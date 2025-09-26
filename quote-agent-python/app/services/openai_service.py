from openai import AsyncOpenAI
import os
import logging
import json
from typing import Dict, List, Tuple, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        """
        Initialize the OpenAI service
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        
        # Initialize OpenAI client if API key is available
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            logger.warning("OpenAI API key not found. Some features will be simulated.")
        
    async def process_conversation(
        self, 
        user_input: str, 
        current_state: str, 
        conversation_context: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Process the conversation with OpenAI
        
        Args:
            user_input: The user's input text
            current_state: The current state of the conversation
            conversation_context: Context information about the conversation
            
        Returns:
            Tuple containing:
            - AI response text
            - New conversation state
            - Extracted information dictionary
        """
        # Build system prompt based on current state
        system_prompt = self._get_system_prompt(current_state)
        
        # Build conversation history
        conversation_history = self._build_conversation_history(conversation_context)
        
        if not self.client:
            # Simulate response if OpenAI client is not available
            return self._simulate_conversation_response(user_input, current_state, conversation_context)
        
        try:
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *conversation_history,
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            response_content = response.choices[0].message.content
            parsed_response = json.loads(response_content)
            
            ai_response = parsed_response.get("response", "")
            new_state = parsed_response.get("new_state", current_state)
            extracted_info = parsed_response.get("extracted_info", {})
            
            logger.info(f"OpenAI processed input: '{user_input[:50]}...', new state: {new_state}")
            
            return ai_response, new_state, extracted_info
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            # Fallback response
            return "I'm sorry, I'm having trouble processing your request. Could you please repeat that?", current_state, {}
    
    def _simulate_conversation_response(self, user_input: str, current_state: str, conversation_context: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """
        Simulate a conversation response when OpenAI API is not available
        
        Args:
            user_input: The user's input text
            current_state: The current state of the conversation
            conversation_context: Context information about the conversation
            
        Returns:
            Tuple containing:
            - AI response text
            - New conversation state
            - Extracted information dictionary
        """
        # Simple rule-based responses based on the current state
        if current_state == "greeting":
            # Extract parts from user input (simple keyword matching)
            parts = []
            for keyword in ["motor", "gearbox", "sensor", "controller", "bearing", "pump", "valve", "switch"]:
                if keyword in user_input.lower():
                    parts.append(keyword)
            
            if parts:
                return (
                    f"I see you need {', '.join(parts)}. Can you provide any specific details about these parts?",
                    "collecting_parts",
                    {"parts": parts}
                )
            else:
                return (
                    "What specific parts are you looking for today?",
                    "greeting",
                    {}
                )
                
        elif current_state == "collecting_parts":
            # Check if user input contains customer information keywords
            if any(keyword in user_input.lower() for keyword in ["name", "email", "phone", "address", "contact"]):
                return (
                    "Great, now I need your contact information. Could you provide your name, phone number, email, and delivery address?",
                    "collecting_info",
                    {}
                )
            else:
                # Extract more parts if mentioned
                parts = []
                for keyword in ["motor", "gearbox", "sensor", "controller", "bearing", "pump", "valve", "switch"]:
                    if keyword in user_input.lower() and keyword not in conversation_context.get("parts_needed", []):
                        parts.append(keyword)
                
                return (
                    "Thank you for those details. Could you also provide your contact information so we can get back to you with quotes?",
                    "collecting_info",
                    {"parts": parts} if parts else {}
                )
                
        elif current_state == "collecting_info":
            # Extract customer information (very simplified)
            customer_info = {}
            
            # Simple extraction of name, email, phone, address
            if "name" in user_input.lower() and "is" in user_input.lower():
                name_start = user_input.lower().find("name is") + 8
                name_end = user_input.find(".", name_start)
                if name_end == -1:
                    name_end = len(user_input)
                customer_info["name"] = user_input[name_start:name_end].strip()
            
            if "@" in user_input:
                # Simple email extraction
                words = user_input.split()
                for word in words:
                    if "@" in word:
                        customer_info["email"] = word.strip(".,;")
                        break
            
            # Check if we have enough information to complete
            if customer_info or "done" in user_input.lower() or "that's all" in user_input.lower():
                return (
                    "Thank you for providing your information. We'll call you back shortly with quotes for your parts.",
                    "completed",
                    {"customer_info": customer_info}
                )
            else:
                return (
                    "Could you please provide your name, email, phone number, and delivery address?",
                    "collecting_info",
                    {}
                )
        
        # Default response for completed state or unknown states
        return (
            "Thank you for your information. We'll call you back shortly with quotes for your parts.",
            "completed",
            {}
        )
    
    def _get_system_prompt(self, current_state: str) -> str:
        """
        Get the appropriate system prompt based on the current conversation state
        
        Args:
            current_state: The current state of the conversation
            
        Returns:
            System prompt string for the given state
        """
        base_prompt = """
        You are an AI assistant for a workshop parts service. Your job is to help customers who call in
        looking for specific parts they need for their workshop. Be professional, helpful, and concise.
        
        Respond in JSON format with the following structure:
        {
            "response": "Your response to the customer",
            "new_state": "The new conversation state",
            "extracted_info": {
                // Information extracted from the customer's speech
            }
        }
        
        Current conversation state: {state}
        """
        
        state_specific_instructions = {
            "greeting": """
            Ask the customer what specific parts they need for their workshop.
            Extract any parts mentioned in their response.
            If parts are mentioned, set new_state to "collecting_parts".
            
            In extracted_info, include:
            {
                "parts": ["part1", "part2", ...]
            }
            """,
            
            "collecting_parts": """
            Confirm the parts the customer has mentioned.
            Ask for any additional details about the parts (specifications, models, etc.).
            When you have enough information about the parts, ask for customer information (name, contact details, delivery address).
            If the customer provides their information, set new_state to "collecting_info".
            
            In extracted_info, include:
            {
                "parts": ["part1", "part2", ...]
            }
            """,
            
            "collecting_info": """
            Collect and confirm customer information (name, phone number, email, delivery address).
            When you have all necessary information, thank the customer and let them know you'll call them back with quotes.
            Set new_state to "completed" when all information is collected.
            
            In extracted_info, include:
            {
                "customer_info": {
                    "name": "...",
                    "phone": "...",
                    "email": "...",
                    "address": "..."
                }
            }
            """,
            
            "completed": """
            The conversation is complete. Thank the customer and let them know you'll call them back with quotes soon.
            """
        }
        
        return base_prompt.format(state=current_state) + state_specific_instructions.get(current_state, "")
    
    def _build_conversation_history(self, conversation_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Build conversation history from context
        
        Args:
            conversation_context: Context information about the conversation
            
        Returns:
            List of message dictionaries for the conversation history
        """
        history = []
        
        # Add system message about parts needed if available
        if "parts_needed" in conversation_context and conversation_context["parts_needed"]:
            parts_list = ", ".join(conversation_context["parts_needed"])
            history.append({
                "role": "system", 
                "content": f"The customer has mentioned needing these parts: {parts_list}"
            })
        
        # Add system message about customer info if available
        if "customer_info" in conversation_context and conversation_context["customer_info"]:
            customer_info = conversation_context["customer_info"]
            info_items = []
            for k, v in customer_info.items():
                if v:  # Only include non-empty values
                    info_items.append(f"{k}: {v}")
            
            if info_items:
                info_str = ", ".join(info_items)
                history.append({
                    "role": "system", 
                    "content": f"Customer information collected so far: {info_str}"
                })
        
        # Add previous conversation messages if available
        if "last_user_input" in conversation_context and "last_ai_response" in conversation_context:
            history.append({
                "role": "user",
                "content": conversation_context["last_user_input"]
            })
            history.append({
                "role": "assistant",
                "content": conversation_context["last_ai_response"]
            })
        
        return history
    
    async def generate_manufacturer_prompt(self, parts_needed: List[str]) -> str:
        """
        Generate a prompt for calling manufacturers
        
        Args:
            parts_needed: List of part names
            
        Returns:
            Prompt string for the manufacturer call
        """
        if not self.client:
            # Fallback prompt if OpenAI client is not available
            return f"Hello, I'm calling from Workshop Parts Assistant to request a quote for the following parts: {', '.join(parts_needed)}. Could you provide pricing and availability information?"
        
        try:
            # Call OpenAI API to generate a natural-sounding prompt
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "Generate a professional prompt for calling a manufacturer to request a quote for specific parts."
                    },
                    {
                        "role": "user", 
                        "content": f"Generate a prompt for calling a manufacturer to get a quote for these parts: {', '.join(parts_needed)}"
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating manufacturer prompt: {str(e)}")
            # Fallback prompt
            return f"Hello, I'm calling from Workshop Parts Assistant to request a quote for the following parts: {', '.join(parts_needed)}. Could you provide pricing and availability information?"
    
    async def extract_quote_info(self, speech: str) -> Dict[str, Any]:
        """
        Extract quote information from manufacturer speech
        
        Args:
            speech: The speech text from the manufacturer
            
        Returns:
            Dictionary with extracted quote information
        """
        if not self.client:
            # Simulate quote extraction if OpenAI client is not available
            return self._simulate_quote_extraction(speech)
        
        try:
            # Call OpenAI API to extract quote information
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        Extract quote information from the manufacturer's response.
                        Return a JSON object with the following structure:
                        {
                            "price": float, // The quoted price
                            "eta": int, // Estimated delivery time in days
                            "parts": ["part1", "part2", ...], // List of parts mentioned
                            "notes": "Any additional notes or conditions"
                        }
                        If certain information is not available, omit that field.
                        """
                    },
                    {
                        "role": "user", 
                        "content": speech
                    }
                ],
                temperature=0.5,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            response_content = response.choices[0].message.content
            parsed_response = json.loads(response_content)
            
            logger.info(f"Extracted quote info: {parsed_response}")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error extracting quote info: {str(e)}")
            # Fallback extraction
            return self._simulate_quote_extraction(speech)
    
    def _simulate_quote_extraction(self, speech: str) -> Dict[str, Any]:
        """
        Simulate quote extraction when OpenAI API is not available
        
        Args:
            speech: The speech text from the manufacturer
            
        Returns:
            Dictionary with simulated quote information
        """
        import re
        import random
        
        quote_info = {}
        
        # Try to extract price
        price_match = re.search(r'\$?(\d+(?:\.\d+)?)', speech)
        if price_match:
            try:
                quote_info["price"] = float(price_match.group(1))
            except ValueError:
                quote_info["price"] = random.uniform(800, 2000)
        else:
            quote_info["price"] = random.uniform(800, 2000)
        
        # Try to extract ETA
        eta_match = re.search(r'(\d+)\s*(?:day|days|business days)', speech, re.IGNORECASE)
        if eta_match:
            try:
                quote_info["eta"] = int(eta_match.group(1))
            except ValueError:
                quote_info["eta"] = random.randint(1, 7)
        else:
            quote_info["eta"] = random.randint(1, 7)
        
        # Extract parts (simple keyword matching)
        parts = []
        for keyword in ["motor", "gearbox", "sensor", "controller", "bearing", "pump", "valve", "switch"]:
            if keyword in speech.lower():
                parts.append(keyword)
        
        if parts:
            quote_info["parts"] = parts
        
        # Add notes if certain keywords are present
        if any(word in speech.lower() for word in ["condition", "warranty", "guarantee", "minimum", "bulk"]):
            quote_info["notes"] = "Some conditions may apply. Contact for details."
        
        return quote_info
