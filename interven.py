import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import google.generativeai as genai
from dotenv import load_dotenv
from fpdf import FPDF

# --- Configuration ---
# Load environment variables from a .env file (e.g., GOOGLE_API_KEY, SENDER_EMAIL)
load_dotenv()

# Configure the Generative AI client with the API key
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    genai.configure(api_key=api_key)
except ValueError as e:
    print(f"AI Initialization Error: {e}")
    # The app will run, but any AI-dependent features will fail.

# --- System Instructions for AI Models ---
CHATBOT_SYSTEM_INSTRUCTION = """You are an AI assistant specialized in patient risk analysis and intervention planning. Your task is to analyze patient medical history, risk factors, and current conditions to provide accurate intervention recommendations.

**Risk Tier Definitions:**
- **Tier 1 (Low Risk):** Patients with stable chronic conditions, low utilization of healthcare services, and low risk of hospitalization. Focus on preventive care and routine check-ups.
- **Tier 2 (Low-Moderate Risk):** Patients with one or more chronic conditions that are generally well-managed but may have occasional exacerbations. Require regular monitoring and patient education.
- **Tier 3 (Moderate Risk):** Patients with multiple chronic conditions, higher healthcare utilization, and a moderate risk of hospitalization. Need coordinated care, medication management, and specialist follow-ups.
- **Tier 4 (High Risk):** Patients with complex medical histories, multiple poorly controlled chronic conditions, recent hospitalizations, and a high risk of readmission. Require intensive care management, frequent follow-ups, and potentially home health services.

- Analyze the patient's risk factors and medical conditions based on the complete data provided.
- Suggest appropriate interventions based on the defined risk tiers and specific clinical indicators.
- Provide evidence-based recommendations for care management.
- **Format your responses using simple Markdown.** Use headings with `**text**` and bullet points with `* item` to structure the information clearly.
- Always include a disclaimer that you are an AI assistant and a real doctor should be consulted.
"""

SUMMARY_SYSTEM_INSTRUCTION = """You are a medical AI assistant. Based on the complete patient data provided, generate a concise clinical summary in about 200 words. Focus on the most critical risk factors, conditions, and the patient's overall risk level. The tone should be objective and professional, intended for a healthcare provider. Do not include a disclaimer."""

INTERVENTION_PLAN_INSTRUCTION = """
You are an AI assistant creating a personalized intervention plan for a patient.
Based on the provided patient data, generate a structured and actionable plan.
The tone should be professional, empathetic, and clear for the patient to understand.

Format the output strictly as follows using Markdown:
- Use `**Section Title**` for main headings (e.g., **Introduction**).
- Use `* Item` for bullet points under each section.

The plan must include these sections:
1.  **Introduction:** A brief, encouraging opening explaining the plan's purpose.
2.  **Key Health Focus Areas:** Identify the top 2-3 health issues from the patient's data (e.g., Heart Health, Diabetes Management).
3.  **Recommended Actions:** For each focus area, provide 3-5 specific, actionable steps (e.g., 'Monitor blood sugar twice daily,' 'Walk for 20 minutes each morning').
4.  **Follow-Up:** Emphasize the importance of the next appointment and staying in touch with the care team.
5.  **Disclaimer:** Include a standard medical disclaimer advising the patient to consult with their healthcare provider before making any changes to their health regimen.
"""

# --- Helper function ---
def _format_patient_context(patient_data):
    """Formats the patient data dictionary into a readable string for the AI prompt."""
    if not patient_data:
        return "No patient data available."
    
    details = ["**Patient Record:**"]
    for key, value in patient_data.items():
        clean_key = key.replace('_', ' ').title()
        
        if 'risk' in key and isinstance(value, float):
            display_value = f"{value:.1%}"
        elif key.startswith('sp_') and value in [0, 1]:
             display_value = 'Yes' if value == 1 else 'No'
        else:
            display_value = value if value is not None else "N/A"
        
        details.append(f"- **{clean_key}:** {display_value}")
            
    return "\n".join(details)

# --- Chatbot Functions ---
def initialize_chat(patient_data=None):
    """Initializes the GenerativeModel for the chatbot with full patient context."""
    try:
        patient_context = _format_patient_context(patient_data)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=CHATBOT_SYSTEM_INSTRUCTION + "\n\n" + patient_context
        )
        chat = model.start_chat(history=[])
        return chat
    except Exception as e:
        print(f"An error occurred during model initialization: {e}")
        return None

def get_ai_response(chat_session, user_input):
    """Sends the user's message to the AI chatbot and gets a response."""
    try:
        response = chat_session.send_message(user_input)
        return response.text
    except Exception as e:
        return f"Error getting AI response: {str(e)}"

# --- AI Summary Function ---
def get_ai_summary(patient_data):
    """Generates a clinical summary for a patient using the AI."""
    try:
        patient_context = _format_patient_context(patient_data)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SUMMARY_SYSTEM_INSTRUCTION
        )
        response = model.generate_content(f"Generate the summary for this patient:\n{patient_context}")
        return response.text
    except Exception as e:
        print(f"Error generating AI summary: {e}")
        return "Could not generate AI summary due to a server error."

# --- PDF and Email Functions ---

class PDF(FPDF):
    """Custom PDF class to define a standard header and footer."""
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Personalized Patient Intervention Plan', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 6, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        body_encoded = body.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 10, body_encoded)
        self.ln()

def generate_intervention_text(patient_data):
    """Generates just the intervention plan text using the AI model."""
    try:
        patient_context = _format_patient_context(patient_data)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=INTERVENTION_PLAN_INSTRUCTION
        )
        prompt = f"Generate the intervention plan for the following patient:\n{patient_context}"
        plan_text = model.generate_content(prompt).text
        return plan_text
    except Exception as e:
        print(f"Error generating intervention text: {e}")
        return "Failed to generate intervention plan. Please check the server logs."

# --- CHANGE: This function now returns the PDF as bytes in memory ---
def generate_intervention_pdf_from_text(patient_data, plan_text):
    """Generates an intervention plan PDF from provided text and returns it as bytes."""
    try:
        pdf = PDF()
        pdf.add_page()
        
        pdf.chapter_title(f"Plan for: {patient_data.get('name', 'N/A')}")
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f"Patient ID: {patient_data.get('desynpuf_id', 'N/A')[:8]}", 0, 1)
        pdf.ln(10)
        
        for line in plan_text.split('\n'):
            line = line.strip()
            if line.startswith('**') and line.endswith('**'):
                pdf.chapter_title(line.replace('**', ''))
            elif line.startswith('* '):
                pdf.set_font('Arial', '', 12)
                body_encoded = f"    •  {line[2:]}".encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 8, body_encoded)
            elif line:
                pdf.chapter_body(line)
        
        # --- CHANGE: Output PDF to a byte string instead of a file ---
        return pdf.output(dest='S').encode('latin-1')
        
    except Exception as e:
        print(f"Error generating PDF from text: {e}")
        return None

# --- CHANGE: This function now accepts PDF byte data instead of a file path ---
def send_intervention_email(receiver_email, pdf_data, patient_name):
    """Sends the intervention plan PDF via email using in-memory data."""
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    
    if not all([sender_email, sender_password]):
        error_msg = "Email credentials (SENDER_EMAIL, SENDER_PASSWORD) are not set."
        print(f"Error: {error_msg}")
        return False, error_msg

    try:
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email
        message['Subject'] = f"Your Personalized Intervention Plan for {patient_name}"
        
        body = f"Dear {patient_name},\n\nPlease find your personalized intervention plan attached to this email.\n\nWe encourage you to review it and discuss it with us during your next appointment.\n\nSincerely,\nYour Healthcare Team"
        message.attach(MIMEText(body, 'plain'))

        # --- CHANGE: Attach the PDF from the in-memory byte string ---
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_data)
        
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename=Intervention_Plan.pdf")
        message.attach(part)

        # Send the email
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        
        success_msg = f"Intervention plan successfully sent to {receiver_email}"
        print(success_msg)
        return True, success_msg
    except Exception as e:
        error_msg = f"Failed to send email: {e}"
        print(error_msg)
        return False, error_msg