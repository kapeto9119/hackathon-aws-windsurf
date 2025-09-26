# Quote Agent IMS

An Inventory Management System (IMS) application that uses Twilio and OpenAI's real-time API to create an AI agent for handling calls. This system automates the process of finding the best quotes for workshop parts by having an AI agent handle customer calls, then automatically contacting manufacturers for quotes, and finally calling the customer back with the best option.

## Project Overview

This project was created for the AWS Windsurf Hackathon to demonstrate the capabilities of AI agents in a real-world business scenario. The system handles the entire workflow from initial customer contact to final order confirmation:

1. **Initial Customer Call**: An AI agent powered by OpenAI answers calls from customers who need parts for their workshop.
2. **Information Collection**: The agent asks specific questions to understand the customer's requirements and collects necessary contact information.
3. **Manufacturer Quotes**: The system automatically calls different manufacturers to get quotes for the required parts.
4. **Quote Comparison**: The system analyzes all quotes to find the best option based on price and delivery time.
5. **Customer Callback**: The system calls the customer back with details of the best quote.
6. **Order Confirmation**: An email is sent to the customer with order details for confirmation.

## Features

- **AI-Powered Conversation**: Uses OpenAI's real-time API for natural conversations with customers and manufacturers
- **Twilio Integration**: Handles incoming and outgoing calls through Twilio's voice API
- **Automated Quote Comparison**: Intelligently selects the best quote based on price and ETA
- **Database Integration**: Stores all call data, quotes, and orders in PostgreSQL database
- **Email Notifications**: Sends order confirmations to customers
- **Dashboard**: Web interface to monitor calls, quotes, and orders

## Tech Stack

- Python 3.9+
- FastAPI
- PostgreSQL (with Docker)
- SQLAlchemy and Alembic for ORM and migrations
- Twilio for call handling
- OpenAI for AI agent conversation
- SMTP for email notifications

## Quick Start

The easiest way to get started is to use the provided start script:

```bash
./start.sh
```

This script will:

1. Create a virtual environment if it doesn't exist
2. Install all dependencies
3. Create a `.env` file from `.env.example` if it doesn't exist
4. Start the PostgreSQL database with Docker
5. Run database migrations
6. Start the application

## Manual Setup

1. Clone the repository

2. Create a virtual environment and activate it:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your API keys (use `.env.example` as a template):

   ```env
   # Twilio Configuration
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   
   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key
   
   # Email Configuration
   EMAIL_HOST=your_smtp_host
   EMAIL_PORT=your_smtp_port
   EMAIL_USER=your_email_user
   EMAIL_PASSWORD=your_email_password
   
   # Database Configuration
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quote_agent
   BASE_URL=http://localhost:8000
   ```

5. Start the PostgreSQL database with Docker:

   ```bash
   docker-compose up -d
   ```

6. Run the database migrations:

   ```bash
   # Generate the initial migration
   python create_migration.py
   
   # Apply the migration
   alembic upgrade head
   ```

7. Run the application:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Usage

### API Documentation

Access the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs)

### Dashboard

Access the admin dashboard at [http://localhost:8000/dashboard](http://localhost:8000/dashboard)

### Twilio Setup

To receive and make calls with Twilio:

1. Create a Twilio account and get your Account SID, Auth Token, and a Twilio phone number
2. Use a service like ngrok to expose your local server to the internet:

   ```bash
   ngrok http 8000
   ```
3. In your Twilio account dashboard, set the webhook URL for your Twilio phone number to:
   - Voice: `https://your-ngrok-url/twilio/incoming-call`

### Testing the System

1. Call your Twilio phone number to start a conversation with the AI agent
2. The agent will ask about the parts you need and collect your information
3. After the call ends, the system will simulate calls to manufacturers to get quotes
4. The system will call you back with the best quote
5. Check your email for the order confirmation

## Project Structure

```
quote-agent-python/
├── app/
│   ├── main.py (FastAPI main application)
│   ├── routes/
│   │   ├── twilio_routes.py (Twilio webhook endpoints)
│   │   ├── dashboard_routes.py (Admin dashboard API)
│   │   └── email_routes.py (Email endpoints)
│   ├── services/
│   │   ├── call_service.py (Handles incoming/outgoing calls)
│   │   ├── openai_service.py (OpenAI integration)
│   │   ├── manufacturer_service.py (Manages manufacturer quotes)
│   │   └── email_service.py (Email notifications)
│   ├── models/
│   │   └── (Data models)
│   └── utils/
│       └── (Helper functions)
├── static/
│   └── (Static files)
└── templates/
    └── (HTML templates)
```
