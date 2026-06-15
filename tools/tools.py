import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests
from langchain_community.tools import DuckDuckGoSearchRun
from livekit.agents import RunContext, function_tool
from livekit.plugins import groq


@function_tool()
async def structural_automation_worker(context: RunContext, user_request: str) -> str:
    """
    Automates complex text processing, coding structures, or logic debugging tasks.
    """
    logging.info(f"Handoff to Groq automation module for task: {user_request}")

    groq_automation_engine = groq.LLM(
        model="llama-3.3-70b-versitile",
        temperature=0.5,
        api_key=os.environ.get(
            "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"
        ),
    )
    system_prompt = (
        "You are Friday's background data processing worker. Analyze the request and "
        "return an ultra-concise, conversational text summary. Do not output markdown, "
        "code headers, symbols, or bullet points."
    )

    try:
        # Groq processes this massive prompt instantly so the audio loop doesn't stutter
        chat_completion = await groq_automation_engine.chat(
            prompt=f"{system_prompt}\n\nTask: {user_request}"
        )
        # Extract and return raw string text back to Gemini's ear
        return chat_completion.choices[0].message.content.strip()

    except Exception as e:
        logging.error(f"Groq tool worker failed: {e}")
        return "The background automation engine encountered a temporary sorting error, sir."


@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str,
) -> str:
    """
    Get the current weather for a given city.
    """
    try:
        response = requests.get(
            f"https://wttr.in/{city}?format=3",
            timeout=10,
        )
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}."


@function_tool()
async def search_web(
    context: RunContext,  # type: ignore
    query: str,
) -> str:
    """
    Search the web using DuckDuckGo.
    """
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}'."


@function_tool()
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None,
) -> str:
    """
    Send an email through Gmail.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address
    """
    try:
        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        # Get credentials from environment variables
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv(
            "GMAIL_APP_PASSWORD"
        )  # Use App Password, not regular password

        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found in environment variables")
            return "Email sending failed: Gmail credentials not configured."

        # Create message
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add CC if provided
        recipients = [to_email]
        if cc_email:
            msg["Cc"] = cc_email
            recipients.append(cc_email)

        # Attach message body
        msg.attach(MIMEText(message, "plain"))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        server.login(gmail_user, gmail_password)

        # Send email
        text = msg.as_string()
        server.sendmail(gmail_user, recipients, text)
        server.quit()

        logging.info(f"Email sent successfully to {to_email}")
        return f"Email sent successfully to {to_email}"

    except smtplib.SMTPAuthenticationError:
        logging.error("Gmail authentication failed")
        return "Email sending failed: Authentication error. Please check your Gmail credentials."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error occurred: {e}")
        return f"Email sending failed: SMTP error - {str(e)}"
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"
