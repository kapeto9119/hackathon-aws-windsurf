from twilio.twiml.voice_response import VoiceResponse, Gather
from app.services.call_service import CallService
from app.services.openai_service import OpenAIService
from app.services.email_service import EmailService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
from sqlalchemy.orm import selectinload
from app.models.models import Call, Customer, Part, Manufacturer, Quote, Order
from datetime import datetime
import os
import logging
import asyncio
import random
import uuid
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManufacturerService:
    def __init__(self):
        """
        Initialize the ManufacturerService
        """
        # Initialize services
        self.call_service = CallService()
        self.openai_service = OpenAIService()
        self.email_service = EmailService()
        
    async def get_quotes(self, customer_phone: str, call_sid: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        Get quotes from manufacturers for the parts needed by the customer
        
        Args:
            customer_phone: Customer's phone number
            call_sid: The original call SID (optional)
            db: Database session (optional)
        """
        if not db:
            logger.error("Database session required for getting quotes")
            return
            
        # Get customer from database
        result = await db.execute(select(Customer).where(Customer.phone == customer_phone))
        customer = result.scalars().first()
        
        if not customer:
            logger.warning(f"Customer with phone {customer_phone} not found")
            return
            
        # Get parts from the call if call_sid is provided
        parts_needed = []
        if call_sid:
            result = await db.execute(
                select(Call).where(Call.call_sid == call_sid)
                .options(selectinload(Call.parts))
            )
            call = result.scalars().first()
            
            if call and call.parts:
                parts_needed = [part.name for part in call.parts]
        
        if not parts_needed:
            # Try to get parts from any recent calls by this customer
            result = await db.execute(
                select(Call).where(Call.customer_id == customer.id)
                .options(selectinload(Call.parts))
                .order_by(Call.created_at.desc())
                .limit(1)
            )
            recent_call = result.scalars().first()
            
            if recent_call and recent_call.parts:
                parts_needed = [part.name for part in recent_call.parts]
        
        if not parts_needed:
            logger.warning(f"No parts specified for customer {customer_phone}")
            return
        
        logger.info(f"Getting quotes for customer {customer_phone} for parts: {parts_needed}")
        
        # Find relevant manufacturers
        manufacturers = await self._get_relevant_manufacturers(parts_needed, db)
        
        if not manufacturers:
            logger.warning("No relevant manufacturers found")
            return
            
        # Get quotes from manufacturers (simulated for demo)
        for manufacturer in manufacturers:
            # Create quote in database
            quote_data = await self._simulate_manufacturer_quote(manufacturer, parts_needed)
            
            # Save quote to database
            quote = Quote(
                manufacturer_id=manufacturer.id,
                price=quote_data["price"],
                eta=quote_data["eta"]
            )
            db.add(quote)
            await db.flush()
            
            # Add parts to quote
            for part_name in parts_needed:
                # Get part from database
                part_result = await db.execute(select(Part).where(Part.name == part_name))
                part = part_result.scalars().first()
                
                if part:
                    quote.parts.append(part)
            
            await db.commit()
            
            logger.info(f"Saved quote from {manufacturer.name}: ${quote_data['price']:.2f}, ETA: {quote_data['eta']} days")
        
        # Find the best quote
        best_quote = await self.get_best_quote(customer_phone, db)
        
        if best_quote:
            # Mark the best quote
            result = await db.execute(select(Quote).where(Quote.id == best_quote["id"]))
            quote = result.scalars().first()
            
            if quote:
                quote.is_best_quote = True
                await db.commit()
            
            # Create order
            order = Order(
                customer_id=customer.id,
                quote_id=best_quote["id"],
                status="pending"
            )
            db.add(order)
            await db.commit()
            
            # Call the customer back with the best quote
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            callback_url = f"{base_url}/twilio/callback?customer={customer_phone}"
            await self.call_service.make_outbound_call(customer_phone, callback_url)
            
            # Send email confirmation if email is available
            if customer.email:
                await self._send_order_confirmation(customer.email, best_quote, parts_needed, order.order_number)
    
    async def _get_relevant_manufacturers(self, parts_needed: List[str], db: AsyncSession) -> List[Manufacturer]:
        """
        Find manufacturers that can provide the needed parts
        
        Args:
            parts_needed: List of part names
            db: Database session
            
        Returns:
            List of relevant manufacturers
        """
        try:
            # Get all manufacturers from database
            result = await db.execute(select(Manufacturer))
            manufacturers = result.scalars().all()
            
            if not manufacturers:
                # Create some sample manufacturers if none exist
                sample_manufacturers = [
                    {
                        "name": "Acme Inc",
                        "phone": "+15551234567",
                        "email": "sales@acme.example.com",
                        "specialties": ["motors", "gearboxes", "electronics"]
                    },
                    {
                        "name": "TechParts Co",
                        "phone": "+15552345678",
                        "email": "quotes@techparts.example.com",
                        "specialties": ["sensors", "controllers", "motors"]
                    },
                    {
                        "name": "MechSupply",
                        "phone": "+15553456789",
                        "email": "orders@mechsupply.example.com",
                        "specialties": ["mechanical parts", "gearboxes", "bearings"]
                    }
                ]
                
                for mfg_data in sample_manufacturers:
                    manufacturer = Manufacturer(
                        name=mfg_data["name"],
                        phone=mfg_data["phone"],
                        email=mfg_data["email"],
                        specialties=mfg_data["specialties"]
                    )
                    db.add(manufacturer)
                
                await db.commit()
                
                # Get the newly created manufacturers
                result = await db.execute(select(Manufacturer))
                manufacturers = result.scalars().all()
            
            # Find relevant manufacturers based on parts needed
            relevant_manufacturers = []
            
            for manufacturer in manufacturers:
                # Check if manufacturer specializes in any of the needed parts
                # This is a simplified matching logic
                specialties = manufacturer.specialties if manufacturer.specialties else []
                
                for part in parts_needed:
                    for specialty in specialties:
                        if part.lower() in specialty.lower() or specialty.lower() in part.lower():
                            if manufacturer not in relevant_manufacturers:
                                relevant_manufacturers.append(manufacturer)
            
            # If no specific matches, include all manufacturers
            if not relevant_manufacturers:
                relevant_manufacturers = manufacturers
            
            return relevant_manufacturers
        except Exception as e:
            logger.error(f"Error finding relevant manufacturers: {str(e)}")
            return []
    
    async def _simulate_manufacturer_quote(self, manufacturer: Manufacturer, parts: List[str]) -> Dict[str, Any]:
        """
        Simulate getting a quote from a manufacturer
        In a real implementation, this would make an actual call to the manufacturer
        
        Args:
            manufacturer: The manufacturer object
            parts: List of part names
            
        Returns:
            Dictionary with quote details
        """
        # Simulate processing time
        await asyncio.sleep(1)
        
        # Generate a random price between $500 and $2000
        base_price = 500 + random.random() * 1500
        
        # Price varies by manufacturer (simulating different pricing strategies)
        # Use manufacturer name to determine pricing strategy
        if "acme" in manufacturer.name.lower():
            price_factor = 1.1  # Premium pricing
        elif "tech" in manufacturer.name.lower():
            price_factor = 1.0  # Standard pricing
        else:
            price_factor = 0.9  # Discount pricing
        
        price = base_price * price_factor * len(parts)
        
        # Generate a random ETA between 1 and 7 days
        eta = random.randint(1, 7)
        
        return {
            "manufacturer_id": manufacturer.id,
            "manufacturer_name": manufacturer.name,
            "parts": parts,
            "price": round(price, 2),
            "eta": eta
        }
    
    async def start_conversation(self, response: VoiceResponse, manufacturer_id: str, db: AsyncSession):
        """
        Start a conversation with a manufacturer
        
        Args:
            response: Twilio VoiceResponse object
            manufacturer_id: Manufacturer's phone number or ID
            db: Database session
        """
        # Find the manufacturer
        result = await db.execute(select(Manufacturer).where(Manufacturer.phone == manufacturer_id))
        manufacturer = result.scalars().first()
        
        if not manufacturer:
            # Try to find by ID
            try:
                manufacturer_id_int = int(manufacturer_id)
                result = await db.execute(select(Manufacturer).where(Manufacturer.id == manufacturer_id_int))
                manufacturer = result.scalars().first()
            except ValueError:
                pass
        
        if not manufacturer:
            response.say("Error: Manufacturer not found.")
            response.hangup()
            return
        
        # Get recent parts needed for quotes
        result = await db.execute(
            select(Part)
            .join(Quote.parts)
            .join(Quote)
            .where(Quote.manufacturer_id == manufacturer.id)
            .order_by(Quote.created_at.desc())
            .limit(5)
        )
        parts = result.scalars().all()
        
        part_names = [part.name for part in parts] if parts else ["motor", "gearbox"]  # Default if no parts found
        
        # Generate prompt for the manufacturer call
        prompt = await self.openai_service.generate_manufacturer_prompt(part_names)
        
        response.say(prompt)
        
        # Gather speech input
        gather = Gather(
            input="speech",
            action="/twilio/manufacturer-response",
            method="POST",
            speechTimeout="auto",
            speechModel="phone_call",
            enhanced="true"
        )
        response.append(gather)
        
        # Add a fallback message
        response.say("I didn't hear anything. Please call back when you're ready to provide a quote.")
    
    async def process_manufacturer_response(self, speech: str, manufacturer_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Process manufacturer response and extract quote information
        
        Args:
            speech: The speech text from the manufacturer
            manufacturer_id: Manufacturer's phone number or ID
            db: Database session
            
        Returns:
            Dictionary with extracted quote information
        """
        # Use OpenAI to extract quote information from speech
        quote_info = await self.openai_service.extract_quote_info(speech)
        
        # Find the manufacturer
        result = await db.execute(select(Manufacturer).where(Manufacturer.phone == manufacturer_id))
        manufacturer = result.scalars().first()
        
        if not manufacturer:
            # Try to find by ID
            try:
                manufacturer_id_int = int(manufacturer_id)
                result = await db.execute(select(Manufacturer).where(Manufacturer.id == manufacturer_id_int))
                manufacturer = result.scalars().first()
            except ValueError:
                logger.warning(f"Manufacturer with ID/phone {manufacturer_id} not found")
                return quote_info
        
        if not manufacturer:
            logger.warning(f"Manufacturer with ID/phone {manufacturer_id} not found")
            return quote_info
        
        # Save quote to database if price and eta are available
        if "price" in quote_info and "eta" in quote_info:
            quote = Quote(
                manufacturer_id=manufacturer.id,
                price=quote_info["price"],
                eta=quote_info["eta"]
            )
            db.add(quote)
            
            # Add parts to quote if available
            if "parts" in quote_info and quote_info["parts"]:
                for part_name in quote_info["parts"]:
                    # Check if part exists
                    part_result = await db.execute(select(Part).where(Part.name == part_name))
                    part = part_result.scalars().first()
                    
                    if part:
                        quote.parts.append(part)
                    else:
                        # Create new part
                        new_part = Part(name=part_name, category="unknown")
                        db.add(new_part)
                        await db.flush()
                        quote.parts.append(new_part)
            
            await db.commit()
            logger.info(f"Saved quote from {manufacturer.name}: ${quote_info['price']:.2f}, ETA: {quote_info['eta']} days")
        
        return quote_info
    
    async def get_best_quote(self, customer_phone: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Get the best quote for a customer based on price and ETA
        
        Args:
            customer_phone: Customer's phone number
            db: Database session
            
        Returns:
            Dictionary with best quote details if available, None otherwise
        """
        try:
            # Get customer from database
            result = await db.execute(select(Customer).where(Customer.phone == customer_phone))
            customer = result.scalars().first()
            
            if not customer:
                logger.warning(f"Customer with phone {customer_phone} not found")
                return {
                    "manufacturer_name": "Unknown",
                    "price": 1000.00,
                    "eta": 3
                }
            
            # Get all quotes for parts requested by this customer
            # This is a simplified approach - in a real app, we would match quotes to specific customer requests
            result = await db.execute(
                select(Quote)
                .options(
                    selectinload(Quote.manufacturer),
                    selectinload(Quote.parts)
                )
                .order_by(Quote.created_at.desc())
                .limit(10)  # Get recent quotes
            )
            quotes = result.scalars().all()
            
            if not quotes:
                logger.warning(f"No quotes found for customer {customer_phone}")
                return {
                    "manufacturer_name": "Unknown",
                    "price": 1000.00,
                    "eta": 3
                }
            
            # Check if there's already a best quote marked
            for quote in quotes:
                if quote.is_best_quote:
                    return {
                        "id": quote.id,
                        "manufacturer_name": quote.manufacturer.name if quote.manufacturer else "Unknown",
                        "price": quote.price,
                        "eta": quote.eta,
                        "parts": [part.name for part in quote.parts]
                    }
            
            # Simple algorithm to find the best quote:
            # Score = price * 0.7 + (eta * 100) * 0.3
            # Lower score is better
            best_quote = min(quotes, key=lambda q: q.price * 0.7 + (q.eta * 100) * 0.3)
            
            # Mark this as the best quote
            best_quote.is_best_quote = True
            await db.commit()
            
            return {
                "id": best_quote.id,
                "manufacturer_name": best_quote.manufacturer.name if best_quote.manufacturer else "Unknown",
                "price": best_quote.price,
                "eta": best_quote.eta,
                "parts": [part.name for part in best_quote.parts]
            }
            
        except Exception as e:
            logger.error(f"Error getting best quote: {str(e)}")
            return {
                "manufacturer_name": "Unknown",
                "price": 1000.00,
                "eta": 3
            }
    
    async def _send_order_confirmation(self, email: str, quote: Dict[str, Any], parts: List[str], order_number: str):
        """
        Send order confirmation email
        
        Args:
            email: Customer's email address
            quote: Quote information
            parts: List of part names
            order_number: Order number
        """
        subject = "Your Parts Order Confirmation"
        body = f"""
        Dear Customer,
        
        Thank you for your order #{order_number}. Here are the details:
        
        Parts: {', '.join(parts)}
        Price: ${quote['price']:.2f}
        Estimated Delivery: {quote['eta']} days
        Supplier: {quote['manufacturer_name']}
        
        Please click the link below to confirm your order:
        https://quote-agent.example.com/confirm/{order_number}
        
        Thank you for your business!
        
        Quote Agent IMS
        """
        
        await self.email_service.send_email(email, subject, body)
