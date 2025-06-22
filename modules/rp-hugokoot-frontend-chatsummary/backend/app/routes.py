from flask import Blueprint, current_app, request
import flask_sse
import requests
import json
from datetime import datetime
import os
import threading


bp = Blueprint('main', __name__)


def _save_chat_and_summarize_task(app, data):
    with app.app_context():
        messages = data.get('messages', [])
        patient_name = data.get('patient_name', 'unknown')
        
        app.logger.debug(f"Starting background task to save chat for patient: {patient_name}")
        flask_sse.sse.publish({'message': 'Saving chat conversation...'}, type='progress')
        
        # Create a timestamp for the filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chat_{patient_name}_{timestamp}.json"
        
        # Create chats directory if it doesn't exist
        chats_dir = os.path.join(app.root_path, 'chats')
        os.makedirs(chats_dir, exist_ok=True)
        
        # Data to be saved
        save_payload = {
            'patient_name': patient_name,
            'timestamp': timestamp,
            'messages': messages
        }
        
        # Save the chat to a file
        filepath = os.path.join(chats_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(save_payload, f, indent=2)
        
        app.logger.info(f"Chat saved successfully to {filepath}")
        
        # Notify other modules about the saved chat
        reasoner_address = app.config.get('REASONER_ADDRESS', None)
        if reasoner_address:
            try:
                requests.post(f"http://{reasoner_address}/chat-saved", json={
                    'patient_name': patient_name,
                    'chat_file': filename
                })
                app.logger.info(f'Successfully notified reasoner about saved chat: {filename}')
            except Exception as e:
                app.logger.error(f"Failed to notify reasoner about saved chat: {str(e)}")

        # Helper function to call Gemini API - now defined inside the task
        def call_gemini(prompt_text, api_url, generation_config_override=None):
            payload = {
                'contents': [{'role': 'user', 'parts': [{'text': prompt_text}]}],
                'generationConfig': {
                    'temperature': 1,
                    'topK': 1,
                    'topP': 1,
                    'maxOutputTokens': 8192,
                    'stopSequences': []
                },
                'safetySettings': [
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'}
                ]
            }

            if generation_config_override:
                payload['generationConfig'].update(generation_config_override)

            try:
                response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
                response.raise_for_status()
                gemini_response_data = response.json()
                
                if gemini_response_data.get('candidates') and gemini_response_data['candidates'][0]['content']['parts'][0].get('text'):
                    gemini_text_response = gemini_response_data['candidates'][0]['content']['parts'][0]['text']
                    if gemini_text_response.strip().startswith('```json'):
                        gemini_text_response = gemini_text_response.strip()[7:-3].strip()
                    elif gemini_text_response.strip().startswith('json'):
                        gemini_text_response = gemini_text_response.strip()[4:].strip()
                    return json.loads(gemini_text_response)
                return {"error": "Could not extract text from Gemini response", "raw_response": gemini_response_data}
            except requests.exceptions.RequestException as e:
                app.logger.error(f"Error calling Gemini API: {str(e)}")
                return {"error": "Error calling Gemini API", "details": str(e)}
            except Exception as e:
                app.logger.error(f"An unexpected error occurred during Gemini API call: {str(e)}")
                return {"error": "An unexpected error occurred", "details": str(e)}

        try:
            gemini_api_key = 'AIzaSyCorYVbRED1PcIeyIUreHXco_pq2fRtyoQ' # User provided API Key
            gemini_api_url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}'

            N_SENTENCES, K_EXCERPTS = 12, 12
            system_prompt = """You are a compliance summariser for diabetes patient-bot chats that should 
take note of deception and non-adherence according to the provided indicators.  
Audience: the prescribing doctor who will read a one-page update before the 
next appointment.

================  TASK  ===============================
1. **Adherence & Progress Summary** In < {N} sentences, describe:  
   - What the patient reported doing (diet, medication, activity).  
   - Any successes, struggles, or trends.  
   - Overall adherence status and momentum.  
2. **Risk Flags** List every chat excerpt that matches an indicator below.  
3. Output the exact JSON schema shown at the end.

================  INDICATOR GUIDELINES  ================
- **Inconsistency**  Flag any statement that clashes with the patient's 
earlier chats.
- **Vague / Evasive Language** Watch for hedges (maybe, should, could), 
sweeping generalities (always, everyone), passive phrasing, or missing 
specifics (dates, quantities, names). Low-concreteness wording is a 
hallmark of deceptive replies. Rate severity {low | medium | high}.  
- **Engagement Level** Unusually long, highly detailed stories may 
indicate a crafted (and possibly false) narrative. Either extreme can 
suggest non-adherence or deception; interpret in context. 
- **Gaming the System**  Identify too-perfect self-reports: identical 
answers across check-ins, flawless adherence claims, or copy-pasted text.

================  IMPLICIT-RAG INSTRUCTIONS  ================
Step 1 From the full transcript, **extract up to {K} excerpts 
(30 - 120 words each)** that are most relevant to any indicator above.  
Step 2 Using **only those excerpts**, perform TASK 1 and 2.  
Step 3 Return:

json
{
  "summary": "< {N} sentences>",
  "flags": [
    {
      "indicator": "Inconsistency",
      "excerpt": "...",
      "explanation": "..."
    },
    {
      "indicator": "VagueLanguage",
      "excerpt": "...",
      "explanation": "..."
    }
    /* 0-N more flags */
  ]
}
""".replace('{N}', str(N_SENTENCES)).replace('{K}', str(K_EXCERPTS))

            def format_chat_log(chat_data):
                formatted_messages = []
                log_patient_name = chat_data.get('patient_name', 'Unknown Patient')
                for msg in chat_data.get('messages', []):
                    sender_name = msg.get('user', {}).get('name', 'Unknown')
                    is_human = msg.get('user', {}).get('human', False)
                    prefix = f'{sender_name} (Patient):\t' if is_human else 'Bot:\t'
                    message_content = msg.get("message", "")
                    formatted_messages.append(f'{prefix}{message_content}')
                return f'Chat with {log_patient_name} ({chat_data.get("timestamp", "N/A")}):\n' + '\n'.join(formatted_messages)

            all_chat_texts = ['Current Chat Session:\n' + format_chat_log(save_payload)]
            previous_chat_texts = ['\n\nPrevious Saved Chats:']
            if os.path.exists(chats_dir):
                for chat_file_name in sorted(os.listdir(chats_dir)):
                    if chat_file_name.endswith('.json') and chat_file_name != filename:
                        with open(os.path.join(chats_dir, chat_file_name), 'r') as cf:
                            previous_chat_texts.append(format_chat_log(json.load(cf)))
            if len(previous_chat_texts) > 1:
                all_chat_texts.extend(previous_chat_texts)
            else:
                all_chat_texts.append('\nNo previous chats found.')

            combined_chat_history = '\n\n'.join(all_chat_texts)
            full_prompt_for_summaries = system_prompt + 'Chat History for Analysis: ' + combined_chat_history
            
            flask_sse.sse.publish({'message': 'Generating summary 1/2...'}, type='progress')
            summary1_json = call_gemini(full_prompt_for_summaries, gemini_api_url)

            flask_sse.sse.publish({'message': 'Generating summary 2/2...'}, type='progress')
            summary2_json = call_gemini(full_prompt_for_summaries, gemini_api_url)

            if "error" in summary1_json or "error" in summary2_json:
                app.logger.error("Failed to get two valid summaries from Gemini. Aborting.")
                flask_sse.sse.publish({'message': 'Failed to generate summaries.', 'status': 'error'}, type='progress')
                return

            # Save intermediate summaries
            intermediate_dir = os.path.join(chats_dir, 'intermediate_summaries')
            os.makedirs(intermediate_dir, exist_ok=True)
            with open(os.path.join(intermediate_dir, f"summary_{patient_name}_{timestamp}_1.json"), 'w') as f:
                json.dump(summary1_json, f, indent=2)
            with open(os.path.join(intermediate_dir, f"summary_{patient_name}_{timestamp}_2.json"), 'w') as f:
                json.dump(summary2_json, f, indent=2)

            comparison_system_prompt = """You are a verification and synthesis AI. Your task is to analyze two 
different AI-generated summaries and their corresponding 'flags' based 
on the same source text. Your goal is to produce a single, more 
accurate and reliable final JSON output.

You will receive a JSON object with four keys: "summary1", "flags1", 
"summary2", and "flags2".

**Your task is to perform two main actions:**

**1. Synthesize the Summaries:**
   - Read both `summary1` and `summary2`.
   - Combine their insights to create a single, more comprehensive 
   and accurate final summary.
   - The final summary should be objective and reflect the consensus 
   between the two inputs.

**2. Verify and Consolidate the Flags:**
   - Compare `flags1` and `flags2` to identify semantically equivalent flags.
   - A **Direct Match** occurs when a flag from one list clearly refers to 
   the same event or statement as a flag in the other list, even if the 
   wording differs slightly. Matched flags should be included once in the 
   final list without any 'confidence' field.
   - A **Mismatch** occurs when a flag from either list does NOT have a clear 
   semantic equivalent in the other. Mismatched flags MUST have a 
   `"confidence": "low"` field added to them.
   - The final list of flags should not contain duplicates.

**Output Instructions:**
You MUST return a single, valid JSON object with two top-level keys:
- `"summary"`: The new, synthesized summary string.
- `"flags"`: The final, consolidated list of flag objects.
"""
            comparison_input = {
                "summary1": summary1_json.get("summary"), "flags1": summary1_json.get("flags", []),
                "summary2": summary2_json.get("summary"), "flags2": summary2_json.get("flags", [])
            }
            full_comparison_prompt = f"{comparison_system_prompt}\n\n{json.dumps(comparison_input, indent=2)}"
            
            flask_sse.sse.publish({'message': 'Synthesizing final summary...'}, type='progress')
            final_summary_json = call_gemini(full_comparison_prompt, gemini_api_url, generation_config_override={"response_mime_type": "application/json"})

            if "error" in final_summary_json:
                app.logger.error("Failed to get a valid synthesized summary from Gemini.")
                flask_sse.sse.publish({'message': 'Failed to synthesize summary.', 'status': 'error'}, type='progress')
                return

            summary_filename = f"summary_{patient_name}_{timestamp}.txt"
            summary_filepath = os.path.join(chats_dir, summary_filename)
            with open(summary_filepath, 'w') as f_summary:
                f_summary.write("Synthesized Summary from Gemini API:\n" + "="*37 + "\n\n")
                f_summary.write(f"Patient Name: {patient_name}\nTimestamp: {timestamp}\n\n" + "-"*20 + "\n")
                f_summary.write(json.dumps(final_summary_json, indent=2))
            
            app.logger.info(f"Synthesized Gemini API response saved to {summary_filepath}")
            flask_sse.sse.publish({'message': 'Done! Summary saved.', 'status': 'done'}, type='progress')

        except Exception as e:
            app.logger.error(f"An unexpected error occurred during Gemini API integration: {str(e)}")
            flask_sse.sse.publish({'message': 'An unexpected error occurred.', 'status': 'error'}, type='progress')


@bp.route('/')
def hello():
    return 'Hello, I am the website backend module!'


@bp.route('/process', methods=['POST'])
def response():
    data = request.json
    flask_sse.sse.publish({'message': data['message']}, type='response')
    return "Message sent!"


@bp.route('/submit', methods=['POST'])
def submit():
    data = request.json
    
    t2t_address = current_app.config.get("TRIPLE_EXTRACTOR_ADDRESS", None)
    if t2t_address:
        requests.post(f"http://{t2t_address}/process", json=data)

    return f"Submitted sentence '{data['sentence']}' from {data['patient_name']} to t2t!"


@bp.route('/save-chat', methods=['POST'])
def save_chat():
    data = request.json
    if not data.get('messages', []):
        current_app.logger.warning("No messages received, nothing to save.")
        return "No messages to save", 400
        
    thread = threading.Thread(target=_save_chat_and_summarize_task, args=(current_app._get_current_object(), data))
    thread.daemon = True
    thread.start()
    
    return "Save process initiated", 202
