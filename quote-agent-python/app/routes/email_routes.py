from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, EmailStr
from app.services.email_service import EmailService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/email",
    tags=["email"],
    responses={404: {"description": "Not found"}},
)

# Initialize email service
email_service = EmailService()

class EmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str

@router.post("/send")
async def send_email(email_request: EmailRequest, background_tasks: BackgroundTasks):
    """
    Send an email
    """
    try:
        background_tasks.add_task(
            email_service.send_email,
            email_request.recipient,
            email_request.subject,
            email_request.body
        )
        return {"message": "Email sending initiated"}
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.post("/send-order-confirmation")
async def send_order_confirmation(customer_id: str, order_id: str, background_tasks: BackgroundTasks):
    """
    Send order confirmation email
    """
    try:
        # This would typically fetch customer email from a database
        # For demo purposes, using a placeholder
        customer_email = f"{customer_id}@example.com"
        
        # Get order details
        # This would typically fetch from a database
        order_details = {
            "id": order_id,
            "parts": ["motor", "gearbox"],
            "price": 1100.00,
            "eta": 3,
            "manufacturer": "MechSupply"
        }
        
        # Generate email content
        subject = f"Order Confirmation #{order_id}"
        body = f"""
        Dear Customer,
        
        Thank you for your order. Here are the details:
        
        Order ID: {order_id}
        Parts: {', '.join(order_details['parts'])}
        Price: ${order_details['price']:.2f}
        Estimated Delivery: {order_details['eta']} days
        Supplier: {order_details['manufacturer']}
        
        Please click the link below to confirm your order:
        https://quote-agent.example.com/confirm/{order_id}
        
        Thank you for your business!
        
        Quote Agent IMS
        """
        
        background_tasks.add_task(
            email_service.send_email,
            customer_email,
            subject,
            body
        )
        
        return {"message": "Order confirmation email sending initiated"}
    except Exception as e:
        logger.error(f"Error sending order confirmation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send order confirmation: {str(e)}")
