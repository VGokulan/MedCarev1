import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Database configuration
db_config = {
    "host": "medcare.postgres.database.azure.com",
    "database": "postgres",
    "user": "medical",
    "password": "Cts123456",
    "port": "5432"
}


def get_db_connection():
    """Establish connection to Azure PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            port=db_config['port'],
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

def execute_query(query, params=None):
    """Execute SQL query and return results as list of dictionaries"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
    except Exception as e:
        print(f"Error executing query: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_patient_list(search='', risk_tier='', age_range='', limit=10, offset=0):
    """Get list of patients with optional filtering and pagination"""
    base_query = """
    SELECT 
        pa.DESYNPUF_ID as id,
        COALESCE(p.name, 'Patient ' || SUBSTRING(pa.DESYNPUF_ID FROM 1 FOR 8)) as name,
        pa.age,
        pa.risk_tier,
        CONCAT(
            CASE WHEN pa.SP_CHF = 1 THEN 'CHF, ' ELSE '' END,
            CASE WHEN pa.SP_DIABETES = 1 THEN 'Diabetes, ' ELSE '' END,
            CASE WHEN pa.SP_COPD = 1 THEN 'COPD, ' ELSE '' END,
            CASE WHEN pa.SP_ISCHMCHT = 1 THEN 'Ischemic Heart, ' ELSE '' END,
            CASE WHEN pa.SP_DEPRESSN = 1 THEN 'Depression, ' ELSE '' END
        ) as conditions
    FROM patient_analysis pa
    LEFT JOIN patients p ON pa.DESYNPUF_ID = p.DESYNPUF_ID
    WHERE 1=1
    """
    
    params = []
    
    if search:
        base_query += " AND (pa.DESYNPUF_ID ILIKE %s OR CAST(pa.age AS TEXT) ILIKE %s OR p.name ILIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    if risk_tier and risk_tier != '':
        base_query += " AND pa.risk_tier = %s"
        params.append(risk_tier)
    
    if age_range:
        if age_range == '18-30':
            base_query += " AND pa.age BETWEEN 18 AND 30"
        elif age_range == '31-50':
            base_query += " AND pa.age BETWEEN 31 AND 50"
        elif age_range == '51-70':
            base_query += " AND pa.age BETWEEN 51 AND 70"
        elif age_range == '70+':
            base_query += " AND pa.age >= 70"
    
    base_query += " ORDER BY pa.risk_tier DESC, pa.hospitalization_30d_score DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    count_query = """
    SELECT COUNT(*) 
    FROM patient_analysis pa
    LEFT JOIN patients p ON pa.DESYNPUF_ID = p.DESYNPUF_ID
    WHERE 1=1
    """
    
    count_params = []
    if search:
        count_query += " AND (pa.DESYNPUF_ID ILIKE %s OR CAST(pa.age AS TEXT) ILIKE %s OR p.name ILIKE %s)"
        count_params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    if risk_tier and risk_tier != '':
        count_query += " AND pa.risk_tier = %s"
        count_params.append(risk_tier)
    
    if age_range:
        if age_range == '18-30':
            count_query += " AND pa.age BETWEEN 18 AND 30"
        elif age_range == '31-50':
            count_query += " AND pa.age BETWEEN 31 AND 50"
        elif age_range == '51-70':
            count_query += " AND pa.age BETWEEN 51 AND 70"
        elif age_range == '70+':
            count_query += " AND pa.age >= 70"
    
    total_count = execute_query(count_query, count_params)
    total_records = total_count[0]['count'] if total_count else 0
    
    results = execute_query(base_query, params)
    
    formatted_results = []
    for row in results:
        risk_tier_str = str(row['risk_tier']) if row['risk_tier'] else '1'
        risk_tier_num = int(risk_tier_str) if risk_tier_str.isdigit() else 1
        
        formatted_results.append({
            "id": row['id'],
            "full_id": row['id'],
            "name": row['name'],
            "age": row['age'],
            "risk_tier": risk_tier_num,
            "risk_tier_display": f"Tier {risk_tier_str}",
            "conditions": row['conditions'].rstrip(', ') if row['conditions'] else 'No conditions'
        })
    
    return formatted_results, total_records

def get_patient_filters():
    """Get available filter options for patients"""
    risk_tiers_query = "SELECT DISTINCT risk_tier FROM patient_analysis WHERE risk_tier IS NOT NULL ORDER BY risk_tier"
    risk_tiers = execute_query(risk_tiers_query)
    
    numeric_tiers = []
    for tier in risk_tiers:
        tier_str = str(tier['risk_tier'])
        if tier_str.isdigit():
            numeric_tiers.append(int(tier_str))
    
    return {
        "risk_tiers": sorted(numeric_tiers),
        "age_ranges": ['18-30', '31-50', '51-70', '70+']
    }

def delete_patient(patient_id):
    """Delete a patient from both tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        delete_query_analysis = "DELETE FROM patient_analysis WHERE DESYNPUF_ID = %s"
        cursor.execute(delete_query_analysis, (patient_id,))
        
        delete_query_patients = "DELETE FROM patients WHERE DESYNPUF_ID = %s"
        cursor.execute(delete_query_patients, (patient_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error deleting patient: {e}")
        return False
    
def get_patient_details(patient_id):
    """Get detailed information for a specific patient by joining tables."""
    query = """
    SELECT 
        pa.*,
        p.name,
        CASE WHEN pa.gender_male = 1 THEN 'Male' ELSE 'Female' END as gender,
        CASE 
            WHEN pa.race_white = 1 THEN 'White' 
            WHEN pa.race_black = 1 THEN 'Black'
            ELSE 'Other' 
        END as race
    FROM patient_analysis pa
    LEFT JOIN patients p ON pa.DESYNPUF_ID = p.DESYNPUF_ID
    WHERE pa.DESYNPUF_ID = %s
    """
    
    result = execute_query(query, (patient_id,))
    return result[0] if result else None