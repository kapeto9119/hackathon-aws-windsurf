from fastapi import APIRouter, Request, Response, Depends, BackgroundTasks, HTTPException
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.request_validator import RequestValidator
from app.services.call_service import CallService
from app.services.manufacturer_service import ManufacturerService
from app.models.base import get_db
from app.models.models import Call, Customer, Part
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload
import os
import logging
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/twilio",
    tags=["twilio"],
    responses={404: {"description": "Not found"}},
)

# Initialize services
call_service = CallService()
manufacturer_service = ManufacturerService()

# Twilio request validation
twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
validator = RequestValidator(twilio_auth_token) if twilio_auth_token else None

async def validate_twilio_request(request: Request):
    """
    Validate that the request is coming from Twilio
    """
    if not validator:
        # Skip validation if no auth token is set (for development)
        return True
        
    # Get the URL and POST data
    url = str(request.url)
    form_data = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # Validate the request
    return validator.validate(url, dict(form_data), signature)

async def save_call_to_db(db: AsyncSession, call_sid: str, caller: str, direction: str):
    """
    Save call information to the database
    """
    try:
        # Check if customer exists
        result = await db.execute(select(Customer).where(Customer.phone == caller))
        customer = result.scalars().first()
        
        if not customer:
            # Create new customer
            customer = Customer(phone=caller)
            db.add(customer)
            await db.flush()
        
        # Create call record
        call = Call(
            call_sid=call_sid,
            customer_id=customer.id,
            direction=direction,
            status="in-progress",
            conversation_data={"state": "greeting"}
        )
        db.add(call)
        await db.commit()
        
        return call
    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving call to database: {str(e)}")
        return None

@router.post("/incoming-call")
async def handle_incoming_call(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Handle incoming customer calls
    """
    # Validate request (commented out for development)
    # if not await validate_twilio_request(request):
    #     raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    
    form_data = await request.form()
    caller = form_data.get("From", "unknown")
    call_sid = form_data.get("CallSid", "")
    
    logger.info(f"Incoming call from {caller} with SID {call_sid}")
    
    # Save call to database
    await save_call_to_db(db, call_sid, caller, "inbound")
    
    # Create TwiML response
    response = VoiceResponse()
    
    # Start conversation with AI agent
    greeting = (
        "Hello, this is the Workshop Parts Assistant. "
        "I understand you're missing some parts for your workshop. "
        "I'm here to help you get what you need. "
        "Could you please tell me what parts you're looking for?"
    )
    
    response.say(greeting)
    
    # Gather speech input
    gather = Gather(
        input="speech",
        action="/twilio/ai-response",
        method="POST",
        speechTimeout="auto",
        speechModel="phone_call",
        enhanced="true"
    )
    
    # Add a fallback message in case the user doesn't speak
    response.append(gather)
    response.say("I didn't hear anything. Please call back when you're ready to discuss your parts needs.")
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/ai-response")
async def handle_ai_response(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Handle AI agent responses during the call
    """
    form_data = await request.form()
    caller = form_data.get("From", "unknown")
    call_sid = form_data.get("CallSid", "")
    speech_result = form_data.get("SpeechResult", "")
    
    logger.info(f"Received speech from {caller}: {speech_result}")
    
    # Get call from database
    result = await db.execute(
        select(Call).where(Call.call_sid == call_sid)
        .options(selectinload(Call.customer))
    )
    call = result.scalars().first()
    
    if not call:
        logger.warning(f"Call {call_sid} not found in database")
        # Create a new call record if not found
        call = await save_call_to_db(db, call_sid, caller, "inbound")
    
    # Process speech with AI and get response
    ai_response, new_state, extracted_info = await call_service.process_speech(speech_result, call)
    
    # Update call in database
    if call:
        # Create new conversation data dictionary
        new_conversation_data = {
            "state": new_state,
            "last_user_input": speech_result,
            "last_ai_response": ai_response
        }
        
        # Add existing conversation data if available
        if call.conversation_data:
            for key, value in call.conversation_data.items():
                if key not in new_conversation_data:
                    new_conversation_data[key] = value
                    
        call.conversation_data = new_conversation_data
        
        # If parts were extracted, add them to the database
        if "parts" in extracted_info and extracted_info["parts"]:
            for part_name in extracted_info["parts"]:
                # Check if part exists
                part_result = await db.execute(select(Part).where(Part.name == part_name))
                part = part_result.scalars().first()
                
                if not part:
                    # Create new part
                    part = Part(name=part_name, category="unknown")
                    db.add(part)
                    await db.flush()
                
                # Add part to call if not already added
                if part not in call.parts:
                    call.parts.append(part)
        
        # If customer info was extracted, update customer
        if "customer_info" in extracted_info and extracted_info["customer_info"]:
            customer = call.customer
            if customer:
                for key, value in extracted_info["customer_info"].items():
                    if hasattr(customer, key) and value:
                        setattr(customer, key, value)
        
        await db.commit()
    
    # Create TwiML response
    response = VoiceResponse()
    response.say(ai_response)
    
    # If conversation is complete, queue manufacturer calls
    if new_state == "completed":
        # Update call status
        if call:
            call.status = "completed"
            await db.commit()
            
        # Queue background task to get quotes
        background_tasks.add_task(manufacturer_service.get_quotes, caller, call_sid if call else None)
        response.say("Thank you for your information. I'll call you back shortly with the best quote.")
        response.hangup()
    else:
        # Continue gathering speech
        gather = Gather(
            input="speech",
            action="/twilio/ai-response",
            method="POST",
            speechTimeout="auto",
            speechModel="phone_call",
            enhanced="true"
        )
        response.append(gather)
        
        # Add a fallback message
        response.say("I didn't hear anything. Please call back when you're ready to continue.")
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/manufacturer-call")
async def handle_manufacturer_call(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle outbound calls to manufacturers
    """
    form_data = await request.form()
    manufacturer_id = form_data.get("To", "unknown")
    call_sid = form_data.get("CallSid", "")
    
    logger.info(f"Manufacturer call connected to {manufacturer_id} with SID {call_sid}")
    
    # Save call to database
    await save_call_to_db(db, call_sid, manufacturer_id, "outbound")
    
    # Create TwiML response
    response = VoiceResponse()
    
    # Start conversation with manufacturer
    await manufacturer_service.start_conversation(response, manufacturer_id, db)
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/manufacturer-response")
async def handle_manufacturer_response(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle manufacturer responses during the call
    """
    form_data = await request.form()
    manufacturer_id = form_data.get("To", "unknown")
    call_sid = form_data.get("CallSid", "")
    speech_result = form_data.get("SpeechResult", "")
    
    logger.info(f"Received speech from manufacturer {manufacturer_id}: {speech_result}")
    
    # Process manufacturer response
    quote_info = await manufacturer_service.process_manufacturer_response(speech_result, manufacturer_id, db)
    
    # Create TwiML response
    response = VoiceResponse()
    
    # Thank the manufacturer
    response.say("Thank you for providing the quote. We'll be in touch if the customer selects your offer.")
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/callback")
async def handle_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle callbacks to customers with quote information
    """
    form_data = await request.form()
    customer_phone = form_data.get("To", "unknown")
    call_sid = form_data.get("CallSid", "")
    
    logger.info(f"Callback to customer {customer_phone} with SID {call_sid}")
    
    # Save call to database
    await save_call_to_db(db, call_sid, customer_phone, "outbound")
    
    # Get customer from database
    result = await db.execute(select(Customer).where(Customer.phone == customer_phone))
    customer = result.scalars().first()
    
    # Get best quote information
    best_quote = await manufacturer_service.get_best_quote(customer_phone, db)
    
    # Create TwiML response
    response = VoiceResponse()
    
    # Inform customer about the best quote
    callback_message = (
        f"Hello{', ' + customer.name if customer and customer.name else ''}, this is the Quote Agent calling back. "
        f"We've found the best quote for your parts. "
        f"The price is {best_quote['price']} dollars with an estimated delivery time of {best_quote['eta']} days. "
        f"We've sent the order details to your email for confirmation. "
        f"Thank you for using our service!"
    )
    
    response.say(callback_message)
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")

@router.get("/calls")
async def get_calls(db: AsyncSession = Depends(get_db)):
    """
    Get all calls
    """
    result = await db.execute(
        select(Call).options(
            selectinload(Call.customer),
            selectinload(Call.parts)
        )
    )
    calls = result.scalars().all()
    
    return [
        {
            "id": call.id,
            "call_sid": call.call_sid,
            "direction": call.direction,
            "status": call.status,
            "duration": call.duration,
            "customer": {
                "id": call.customer.id,
                "name": call.customer.name,
                "phone": call.customer.phone
            } if call.customer else None,
            "parts": [
                {"id": part.id, "name": part.name, "category": part.category}
                for part in call.parts
            ],
            "created_at": call.created_at.isoformat() if call.created_at else None
        }
        for call in calls
    ]
