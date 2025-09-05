from flask import Flask, render_template, jsonify, request
from data import get_patient_list, get_patient_details, get_patient_filters, delete_patient, execute_query
from predictor import process_uploaded_data, get_conditional_risk_analysis
from interven import initialize_chat, get_ai_response, get_ai_summary, generate_intervention_text, generate_intervention_pdf_from_text, send_intervention_email
import json
import os
import socket # Import the socket library to catch specific network errors

app = Flask(__name__)

# This app is designed for demonstration and educational purposes.
# For a production environment, consider more robust session management.
chat_sessions = {}

@app.route('/')
def index():
    """Renders the main patient list page with filtering and pagination."""
    try:
        # Get query parameters for filtering and pagination
        search = request.args.get('search', '')
        risk_tier = request.args.get('risk_tier', '')
        age_range = request.args.get('age_range', '')
        page = int(request.args.get('page', 1))
        
        limit = 10
        offset = (page - 1) * limit
        
        # Fetch patient data from the database
        patients, total_records = get_patient_list(
            search=search, 
            risk_tier=risk_tier, 
            age_range=age_range,
            limit=limit,
            offset=offset
        )
        
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
        filter_options = get_patient_filters()
        
        # Render the main page with the fetched data
        return render_template('index.html', 
                             patients=patients,
                             total_records=total_records,
                             total_pages=total_pages,
                             current_page=page,
                             filter_options=filter_options,
                             current_filters={
                                 'search': search,
                                 'risk_tier': risk_tier,
                                 'age_range': age_range
                             })
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('error.html', error="Could not load patient list.")

@app.route('/patient/<patient_id>')
def patient_detail(patient_id):
    """Renders the detailed view for a single patient."""
    try:
        patient = get_patient_details(patient_id)
        if not patient:
            return render_template('error.html', error='Patient not found'), 404
        
        return render_template('patient_detail.html', patient=patient)
        
    except Exception as e:
        print(f"Error in patient_detail route for ID {patient_id}: {e}")
        return render_template('error.html', error="Could not load patient details.")

@app.route('/dashboard')
def dashboard():
    """Renders the analytics dashboard page."""
    try:
        filter_options = get_patient_filters()
        return render_template('dashboard.html', filter_options=filter_options)
    except Exception as e:
        print(f"Error in dashboard route: {e}")
        return render_template('error.html', error="Could not load dashboard.")
        
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handles data upload and prediction for new patients."""
    if request.method == 'GET':
        return render_template('upload.html')
    else:
        try:
            form_data = request.form.to_dict()
            results = process_uploaded_data(form_data)
            return jsonify(results)
        except Exception as e:
            print(f"Error processing uploaded data: {e}")
            return jsonify({'error': str(e)}), 500

# --- API ENDPOINTS ---

@app.route('/api/patient/<patient_id>', methods=['DELETE'])
def api_delete_patient(patient_id):
    """API endpoint to delete a patient record."""
    try:
        success = delete_patient(patient_id)
        if success:
            return jsonify({'success': True, 'message': 'Patient deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete patient from database'}), 500
    except Exception as e:
        print(f"Error in delete patient API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard_data')
def api_dashboard_data():
    """API endpoint to provide aggregated data for the dashboard charts."""
    try:
        risk_tier = request.args.get('risk_tier', '')
        age_range = request.args.get('age_range', '')
        
        # --- Build SQL query with filters ---
        base_query_from = "FROM patient_analysis"
        where_clauses = ["WHERE 1=1"]
        params = []

        if risk_tier:
            where_clauses.append("risk_tier = %s")
            params.append(int(risk_tier))
        
        age_map = {'18-30': "age BETWEEN 18 AND 30", '31-50': "age BETWEEN 31 AND 50", '51-70': "age BETWEEN 51 AND 70", '70+': "age >= 70"}
        if age_range in age_map:
            where_clauses.append(age_map[age_range])
        
        final_where_clause = " ".join(where_clauses)

        # --- Execute queries for different charts ---
        risk_scores_query = f"SELECT AVG(risk_30d_hospitalization) as avg_30d, AVG(risk_60d_hospitalization) as avg_60d, AVG(risk_90d_hospitalization) as avg_90d {base_query_from} {final_where_clause};"
        risk_scores_data = execute_query(risk_scores_query, params)[0]

        tier_where_clauses = ["WHERE risk_tier IS NOT NULL"]
        if age_range in age_map:
            tier_where_clauses.append(age_map[age_range])
        tier_final_where = " ".join(tier_where_clauses)
        risk_tier_distribution_query = f"SELECT risk_tier, COUNT(*) as count FROM patient_analysis {tier_final_where} GROUP BY risk_tier ORDER BY risk_tier;"
        risk_tier_data = execute_query(risk_tier_distribution_query)

        roi_query = f"SELECT SUM(annual_intervention_cost) as total_costs, SUM(cost_savings) as total_savings {base_query_from} {final_where_clause};"
        roi_data = execute_query(roi_query, params)[0]

        return jsonify({
            'risk_scores': {
                'avg_30d': risk_scores_data.get('avg_30d', 0) or 0,
                'avg_60d': risk_scores_data.get('avg_60d', 0) or 0,
                'avg_90d': risk_scores_data.get('avg_90d', 0) or 0
            },
            'risk_tier_distribution': risk_tier_data,
            'intervention_roi': {
                'total_costs': roi_data.get('total_costs', 0) or 0,
                'total_savings': roi_data.get('total_savings', 0) or 0
            }
        })
    except Exception as e:
        print(f"Error in dashboard data API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conditional_risk/<patient_id>')
def api_conditional_risk(patient_id):
    """API endpoint for condition-specific risk factor analysis."""
    try:
        analysis = get_conditional_risk_analysis(patient_id)
        return jsonify(analysis)
    except Exception as e:
        print(f"Error in conditional risk API: {e}")
        return jsonify({'error': 'Failed to calculate conditional risk analysis.'}), 500

@app.route('/api/ai_summary/<patient_id>')
def api_ai_summary(patient_id):
    """API endpoint to generate a concise AI summary for a patient."""
    try:
        patient_data = get_patient_details(patient_id)
        if not patient_data:
            return jsonify({'error': 'Patient not found'}), 404
        
        summary = get_ai_summary(patient_data)
        return jsonify({'summary': summary})
    except Exception as e:
        print(f"Error in AI summary API: {e}")
        return jsonify({'error': 'AI summary generation failed.'}), 500

@app.route('/api/generate_intervention_text/<patient_id>')
def api_generate_intervention_text(patient_id):
    """API endpoint to generate the raw text for an intervention plan."""
    try:
        patient_data = get_patient_details(patient_id)
        if not patient_data:
            return jsonify({'error': 'Patient not found'}), 404
        
        plan_text = generate_intervention_text(patient_data)
        
        if plan_text:
            return jsonify({'plan_text': plan_text})
        else:
            return jsonify({'error': 'Failed to generate intervention plan text'}), 500
    except Exception as e:
        print(f"Error in generate_intervention_text API: {e}")
        return jsonify({'error': 'An unexpected server error occurred.'}), 500

@app.route('/api/send_intervention/<patient_id>', methods=['POST'])
def api_send_intervention(patient_id):
    """
    API endpoint to generate and email a PDF intervention plan from provided text.
    Handles detailed error feedback from the email sending function.
    """
    try:
        data = request.json
        email = data.get('email')
        plan_text = data.get('plan_text')

        if not email or not plan_text:
            return jsonify({'success': False, 'error': 'Email address and plan text are required'}), 400

        patient_data = get_patient_details(patient_id)
        if not patient_data:
            return jsonify({'success': False, 'error': 'Patient not found'}), 404

        # --- CHANGE: Generate the PDF as an in-memory byte string ---
        pdf_data = generate_intervention_pdf_from_text(patient_data, plan_text)
        if not pdf_data:
            return jsonify({'success': False, 'error': 'Failed to generate PDF plan'}), 500

        # --- CHANGE: Send the byte string directly ---
        patient_name = patient_data.get('name', 'Patient')
        email_sent, message = send_intervention_email(email, pdf_data, patient_name)

        # --- CHANGE: The os.remove call is no longer needed ---

        if email_sent:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 500
    
    except Exception as e:
        print(f"Error in send_intervention API: {e}")
        return jsonify({'success': False, 'error': 'An unexpected server error occurred.'}), 500

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """API endpoint for the AI assistant chatbot."""
    try:
        data = request.json
        patient_id = data.get('patient_id')
        user_input = data.get('message')
        
        if not patient_id or not user_input:
            return jsonify({'error': 'Missing patient_id or message'}), 400

        patient_data = get_patient_details(patient_id)
        if not patient_data:
            return jsonify({'error': 'Patient not found'}), 404

        # Initialize a new chat session for each request for simplicity
        chat_session = initialize_chat(patient_data)
        if not chat_session:
            return jsonify({'error': 'Could not initialize AI chat session'}), 500
            
        ai_response = get_ai_response(chat_session, user_input)
        
        return jsonify({'response': ai_response})
    except Exception as e:
        print(f"Error in chatbot API: {e}")
        return jsonify({'error': 'Failed to get response from AI assistant.'}), 500

if __name__ == '__main__':
    # Runs the Flask application
    # In a production environment, use a proper WSGI server like Gunicorn or uWSGI
    app.run(debug=True, host='0.0.0.0', port=5000)

