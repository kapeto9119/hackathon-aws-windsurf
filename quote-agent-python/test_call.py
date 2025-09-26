#!/usr/bin/env python3
"""
Test script to simulate an incoming call using the Twilio API
"""
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def simulate_incoming_call():
    """
    Simulate an incoming call by sending a POST request to the /twilio/incoming-call endpoint
    """
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    endpoint = f"{base_url}/twilio/incoming-call"
    
    # Simulate Twilio form data
    form_data = {
        "CallSid": "CA12345678901234567890123456789012",
        "From": "+15551234567",  # Replace with your phone number for testing
        "To": os.getenv("TWILIO_PHONE_NUMBER", "+15559876543"),
        "Direction": "inbound",
        "CallStatus": "in-progress"
    }
    
    print(f"Sending POST request to {endpoint} with data: {json.dumps(form_data, indent=2)}")
    
    try:
        response = requests.post(endpoint, data=form_data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text[:500]}...")  # Print first 500 chars of response
        
        if response.status_code == 200:
            print("\nSimulated call initiated successfully!")
            print("Check your server logs for the conversation flow.")
        else:
            print("\nFailed to simulate call. Check your server logs for errors.")
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    simulate_incoming_call()
