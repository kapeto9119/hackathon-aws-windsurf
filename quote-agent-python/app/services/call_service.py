from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from app.services.openai_service import OpenAIService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.models import Call, Customer, Part
import os
import logging
import json
from typing import Dict, List, Tuple, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CallService:
    def __init__(self):
        """
        Initialize the CallService with Twilio client and OpenAI service
        """
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.client = None
        
        # Initialize Twilio client if credentials are available
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        
        self.openai_service = OpenAIService()
        
    async def process_speech(self, speech: str, call: Call) -> Tuple[str, str, Dict[str, Any]]:
        """
        Process customer speech with OpenAI and return AI response
        
        Args:
            speech: The speech text from the customer
            call: The Call object from the database
            
        Returns:
            Tuple containing:
            - AI response text
            - New conversation state
            - Extracted information dictionary
        """
        # Get current conversation state from call data
        conversation_data = call.conversation_data or {}
        current_state = conversation_data.get("state", "greeting")
        
        # Build conversation context
        conversation_context = {
            "state": current_state,
            "parts_needed": [part.name for part in call.parts] if call.parts else [],
            "customer_info": {
                "name": call.customer.name,
                "phone": call.customer.phone,
                "email": call.customer.email,
                "address": call.customer.address
            } if call.customer else {}
        }
        
        # Use OpenAI to process the speech based on current state
        ai_response, new_state, extracted_info = await self.openai_service.process_conversation(
            speech, current_state, conversation_context
        )
        
        logger.info(f"Processed speech from call {call.call_sid}, new state: {new_state}")
        
        return ai_response, new_state, extracted_info
    
    async def make_outbound_call(self, to_number: str, callback_url: str) -> Optional[str]:
        """
        Make an outbound call using Twilio
        
        Args:
            to_number: The phone number to call
            callback_url: The URL to call when the call is answered
            
        Returns:
            The call SID if successful, None otherwise
        """
        if not self.client:
            logger.error("Twilio client not initialized. Check your environment variables.")
            return None
            
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.twilio_phone_number,
                url=callback_url,
                method="POST"
            )
            
            logger.info(f"Initiated outbound call to {to_number}, SID: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Error making outbound call: {str(e)}")
            return None
    
    async def get_call_details(self, call_sid: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Get call details from the database
        
        Args:
            call_sid: The Twilio Call SID
            db: Database session
            
        Returns:
            Dictionary with call details if found, None otherwise
        """
        try:
            result = await db.execute(
                select(Call).where(Call.call_sid == call_sid)
                .options(
                    selectinload(Call.customer),
                    selectinload(Call.parts)
                )
            )
            call = result.scalars().first()
            
            if not call:
                return None
                
            return {
                "id": call.id,
                "call_sid": call.call_sid,
                "direction": call.direction,
                "status": call.status,
                "customer": {
                    "id": call.customer.id,
                    "name": call.customer.name,
                    "phone": call.customer.phone,
                    "email": call.customer.email,
                    "address": call.customer.address
                } if call.customer else None,
                "parts": [
                    {"id": part.id, "name": part.name, "category": part.category}
                    for part in call.parts
                ],
                "conversation_data": call.conversation_data
            }
        except Exception as e:
            logger.error(f"Error getting call details: {str(e)}")
            return None
    
    async def update_call_status(self, call_sid: str, status: str, db: AsyncSession) -> bool:
        """
        Update call status in the database
        
        Args:
            call_sid: The Twilio Call SID
            status: The new status
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            call = result.scalars().first()
            
            if not call:
                return False
                
            call.status = status
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating call status: {str(e)}")
            return False
            
    async def get_customer_requirements(self, call_sid: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get the customer requirements collected during the conversation
        
        Args:
            call_sid: The Twilio Call SID
            db: Database session
            
        Returns:
            Dictionary with customer requirements
        """
        call_details = await self.get_call_details(call_sid, db)
        
        if not call_details:
            return {}
            
        return {
            "parts_needed": [part["name"] for part in call_details["parts"]],
            "customer_info": call_details["customer"] if call_details["customer"] else {}
        }
