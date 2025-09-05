import pickle
import pandas as pd
import numpy as np
from data import get_db_connection, get_patient_details

class Predictor:
    def __init__(self):
        self.pipeline = None
        self.models = None
        self.feature_columns = None
        self.load_models()

    def load_models(self):
        try:
            with open('preprocessing_pipeline.pkl', 'rb') as f:
                self.pipeline = pickle.load(f)
            with open('risk_models.pkl', 'rb') as f:
                models_data = pickle.load(f)
                self.models = models_data['models']
                self.feature_columns = models_data['feature_columns']
                print(f"Loaded models: {list(self.models.keys())}")
        except Exception as e:
            print(f"Error loading models: {e}")
            raise

    def predict(self, input_data):
        if not self.pipeline or not self.models:
            raise Exception("Models not loaded")
        
        # Normalize all incoming keys to lowercase to match feature_columns
        temp_input = {k.lower(): v for k, v in input_data.items()}

        # Ensure all required feature columns exist, defaulting to 0 if not
        for feature in self.feature_columns:
            if feature not in temp_input:
                temp_input[feature] = 0
                
        input_df = pd.DataFrame([temp_input])
        X_input = input_df[self.feature_columns]
        X_scaled = self.pipeline.transform(X_input)
        
        predictions = {}
        for model_name, model in self.models.items():
            prob = model.predict_proba(X_scaled)[0, 1]
            predictions[f'{model_name}_score'] = prob
            
        return predictions

    def get_condition_impact(self, patient_data):
        if not self.pipeline or not self.models:
            print("Models not loaded, cannot calculate condition impact")
            return {}

        # Base prediction with all conditions present
        base_predictions = self.predict(patient_data)
        # Get the mortality score to show in logs, relevant to this analysis
        base_mortality_risk = base_predictions.get('mortality_score', 0)
        print(f"Base mortality risk for impact calculation: {base_mortality_risk}")

        # List of all condition fields
        condition_fields = ['sp_chf', 'sp_diabetes', 'sp_chrnkidn', 'sp_cncr', 'sp_copd',
                        'sp_depressn', 'sp_ischmcht', 'sp_strketia', 'sp_alzhdmta',
                        'sp_osteoprs', 'sp_ra_oa']

        # Find which conditions the patient actually has
        patient_conditions = [cond for cond in condition_fields if patient_data.get(cond) == 1]
        print(f"Patient conditions for mortality impact: {patient_conditions}")

        if not patient_conditions:
            print("No conditions found for patient to analyze for mortality impact.")
            return {}

        impacts = {}
        condition_name_map = {
            'sp_chf': 'Heart Failure',
            'sp_diabetes': 'Diabetes',
            'sp_chrnkidn': 'Kidney Disease',
            'sp_cncr': 'Cancer',
            'sp_copd': 'COPD',
            'sp_depressn': 'Depression',
            'sp_ischmcht': 'Ischemic Heart',
            'sp_strketia': 'Stroke/TIA',
            'sp_alzhdmta': 'Dementia',
            'sp_osteoprs': 'Osteoporosis',
            'sp_ra_oa': 'Arthritis'
        }

        # --- TARGET THE 'mortality' MODEL FOR THIS ANALYSIS ---
        model = self.models.get('mortality')
        if not model:
            print("Warning: 'mortality' model not found. Cannot calculate condition impact on mortality.")
            return {}
            
        importances = None

        # More robustly check for feature weights
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_[0])
        elif hasattr(model, 'base_estimator'):
            base_estimator = model.base_estimator
            if hasattr(base_estimator, 'feature_importances_'):
                importances = base_estimator.feature_importances_
            elif hasattr(base_estimator, 'coef_'):
                importances = np.abs(base_estimator.coef_[0])

        if importances is not None and self.feature_columns:
            importance_dict = dict(zip(self.feature_columns, importances))
            # Calculate total importance from ONLY the patient's conditions
            total_condition_importance = sum(importance_dict.get(cond, 0) for cond in patient_conditions)

            if total_condition_importance > 0:
                for condition in patient_conditions:
                    condition_importance = importance_dict.get(condition, 0)
                    # Calculate relative impact as a percentage of the total importance from conditions
                    relative_impact = (condition_importance / total_condition_importance) * 100
                    if relative_impact > 0: # Only include conditions with a non-zero impact
                        clean_name = condition_name_map.get(condition, condition)
                        impacts[clean_name] = round(relative_impact, 2)
        
        # If impacts dictionary is still empty after trying to get feature weights, use fallback
        if not impacts and patient_conditions:
            print("Warning: Could not determine feature importance for mortality model. Using fallback distribution.")
            num_conditions = len(patient_conditions)
            for condition in patient_conditions:
                clean_name = condition_name_map.get(condition, condition)
                impacts[clean_name] = round(100 / num_conditions, 2)
                
        print(f"Final mortality impacts: {impacts}")
        return impacts

# Create a global predictor instance
predictor = Predictor()

def get_conditional_risk_analysis(patient_id):
    try:
        patient_data = get_patient_details(patient_id)
        if not patient_data:
            print(f"Patient {patient_id} not found")
            return {}
        
        # Normalize keys from the database to lowercase for the prediction engine
        patient_data_lower = {k.lower(): v for k, v in patient_data.items()}
        
        analysis = predictor.get_condition_impact(patient_data_lower)
        return analysis
    except Exception as e:
        print(f"Error in get_conditional_risk_analysis: {e}")
        return {}

def process_uploaded_data(form_data):
    processed_data = {}
    for key, value in form_data.items():
        if key.upper().startswith('SP_'): continue
        if isinstance(value, str) and value.isdigit(): processed_data[key] = int(value)
        else:
            try: processed_data[key] = float(value)
            except (ValueError, TypeError): processed_data[key] = value
    
    condition_fields_upper = ['SP_CHF', 'SP_DIABETES', 'SP_CHRNKIDN', 'SP_CNCR', 'SP_COPD', 'SP_DEPRESSN', 'SP_ISCHMCHT', 'SP_STRKETIA', 'SP_ALZHDMTA', 'SP_OSTEOPRS', 'SP_RA_OA']
    for field in condition_fields_upper:
        processed_data[field] = 1 if field in form_data else 0
    
    age = processed_data.get('age', 0)
    processed_data['age_65_74'] = 1 if 65 <= age < 75 else 0
    processed_data['age_75_84'] = 1 if 75 <= age < 85 else 0
    processed_data['age_85_plus'] = 1 if age >= 85 else 0
    
    high_impact_list = ['SP_CHF', 'SP_CHRNKIDN', 'SP_CNCR', 'SP_COPD']
    processed_data['high_impact_conditions'] = sum(processed_data.get(cond, 0) for cond in high_impact_list)
    processed_data['prior_hospitalization'] = 1 if processed_data.get('inpatient_admissions', 0) > 0 else 0
    processed_data['frequent_ed_user'] = 1 if processed_data.get('outpatient_visits', 0) > 10 else 0
    processed_data['high_cost_patient'] = 1 if processed_data.get('total_medicare_costs', 0) > 20000 else 0

    processed_data_lower = {k.lower(): v for k, v in processed_data.items()}
    predictions = predictor.predict(processed_data_lower)

    db_predictions = {
        'hospitalization_30d_score': predictions.get('30d_hospitalization_score'),
        'hospitalization_60d_score': predictions.get('60d_hospitalization_score'),
        'hospitalization_90d_score': predictions.get('90d_hospitalization_score'),
        'mortality_score': predictions.get('mortality_score')
    }

    primary_risk_score = db_predictions.get('hospitalization_30d_score') or 0
    if primary_risk_score >= 0.85: risk_tier = 5
    elif primary_risk_score >= 0.65: risk_tier = 4
    elif primary_risk_score >= 0.40: risk_tier = 3
    elif primary_risk_score >= 0.15: risk_tier = 2
    else: risk_tier = 1

    tier_info = {
        1: {'label': 'Low Risk', 'intervention': 'Preventive Care', 'cost': 200, 'rate': 0.02},
        2: {'label': 'Low-Moderate Risk', 'intervention': 'Enhanced Wellness', 'cost': 300, 'rate': 0.05},
        3: {'label': 'Moderate Risk', 'intervention': 'Care Coordination', 'cost': 600, 'rate': 0.15},
        4: {'label': 'High Risk', 'intervention': 'Case Management', 'cost': 800, 'rate': 0.25},
        5: {'label': 'Critical Risk', 'intervention': 'Intensive Management', 'cost': 1000, 'rate': 0.35}
    }
    
    avg_preventable_cost = 10000
    prevention_rate = tier_info[risk_tier]['rate']
    prevented_hospitalizations = primary_risk_score * prevention_rate
    cost_savings = prevented_hospitalizations * avg_preventable_cost

    final_results = {
        **processed_data,
        **db_predictions,
        'risk_tier': risk_tier,
        'risk_tier_label': tier_info[risk_tier]['label'],
        'care_intervention': tier_info[risk_tier]['intervention'],
        'annual_intervention_cost': tier_info[risk_tier]['cost'],
        'prevented_hospitalizations': prevented_hospitalizations,
        'cost_savings': cost_savings,
        'risk_30d_hospitalization': primary_risk_score,
        'risk_60d_hospitalization': db_predictions.get('hospitalization_60d_score'),
        'risk_90d_hospitalization': db_predictions.get('hospitalization_90d_score'),
        'mortality_risk': db_predictions.get('mortality_score'),
    }

    store_prediction_results(final_results)
    return final_results

def store_prediction_results(all_data):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db_data = {k.lower(): v for k, v in all_data.items()}
        for key, value in db_data.items():
            if isinstance(value, (np.integer, np.floating)):
                db_data[key] = value.item()
        
        patient_id = str(db_data.get('desynpuf_id'))
        patient_name = db_data.get('name')

        if patient_name and patient_id:
            cursor.execute("SELECT 1 FROM patients WHERE desynpuf_id = %s", (patient_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE patients SET name = %s WHERE desynpuf_id = %s", (patient_name, patient_id))
            else:
                cursor.execute("INSERT INTO patients (desynpuf_id, name) VALUES (%s, %s)", (patient_id, patient_name))
        
        columns = [
            'desynpuf_id', 'age', 'gender_male', 'race_white', 'race_black', 'chronic_condition_count',
            'high_impact_conditions', 'sp_chf', 'sp_diabetes', 'sp_chrnkidn', 'sp_cncr', 'sp_copd', 
            'sp_depressn', 'sp_ischmcht', 'sp_strketia', 'sp_alzhdmta', 'sp_osteoprs', 'sp_ra_oa',
            'inpatient_admissions', 'inpatient_days', 'outpatient_visits', 'total_medicare_costs', 
            'prior_hospitalization', 'risk_30d_hospitalization', 'risk_60d_hospitalization',
            'risk_90d_hospitalization', 'mortality_risk', 'hospitalization_30d_score', 
            'hospitalization_60d_score', 'hospitalization_90d_score', 'mortality_score', 'risk_tier', 
            'risk_tier_label', 'care_intervention', 'annual_intervention_cost', 'cost_savings', 
            'prevented_hospitalizations'
        ]

        cursor.execute("SELECT 1 FROM patient_analysis WHERE desynpuf_id = %s", (patient_id,))
        if cursor.fetchone():
            update_cols = [col for col in columns if col != 'desynpuf_id']
            set_clause = ", ".join([f"{col} = %s" for col in update_cols])
            query = f"UPDATE patient_analysis SET {set_clause} WHERE desynpuf_id = %s"
            values = [db_data.get(col) for col in update_cols] + [patient_id]
            cursor.execute(query, values)
        else:
            placeholders = ', '.join(['%s'] * len(columns))
            query = f"INSERT INTO patient_analysis ({', '.join(columns)}) VALUES ({placeholders})"
            values = [db_data.get(col) for col in columns]
            cursor.execute(query, values)

        conn.commit()
    except Exception as e:
        print(f"Error storing prediction: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()

