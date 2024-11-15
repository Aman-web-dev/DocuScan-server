from flask import Flask, request, jsonify
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import firebase_admin
from firebase_admin import credentials, storage
from PIL import Image
import io
import re
from flask_cors import CORS
import os


app = Flask(__name__)
CORS(app) 

# Get Firebase credentials from environment variables
firebase_credentials = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),  # ensure newline handling
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
}

# Initialize Firebase Admin SDK
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, {
    'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET")
})

# Initialize Firebase Storage Bucket
bucket = storage.bucket()
@app.route('/upload_and_extract', methods=['POST'])
def upload_and_extract_file():
    try:
        print("Received a request at /upload_and_extract")  # Debug: route check

        # Check if 'file' is in request files
        if 'file' not in request.files:
            print("No file in request")  # Debug: missing file
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        file_type = file.content_type
        print(f"File name received: {file.filename}")  # Debug: file name
        print(f"File type received: {file_type}")       # Debug: file type

        # Determine the type of document (PDF or image)
        if file_type == 'application/pdf':
            doc = DocumentFile.from_pdf(file)
        elif file_type in ['image/jpeg', 'image/png']:
            image = Image.open(io.BytesIO(file.read()))
            doc = DocumentFile.from_images([image])
        else:
            return jsonify({'error': 'Unsupported file type'}), 400

        # Perform OCR
        model = ocr_predictor('db_resnet50', 'crnn_vgg16_bn', pretrained=True)
        out = model(doc)

        # Extracted text output
        text_output = out.render()
        print("Text extracted successfully")  # Debug: successful OCR
        print(text_output)

        # Example: Extract useful fields using regex
        extracted_data = {}

        # Example patterns
        patterns = {
            'name': r'NAME\s+([A-Z\s]+)',
            'dob': r'DOB\s+(\d{2}[-/]\d{2}[-/]\d{4})',
            'license_number': r'LICEN[CS]E\s+NO\s+([A-Z0-9]+)',
            'valid_till': r'Valid till \(Non Trans\)\s+(\d{2}[-/]\d{2}[-/]\d{4})',
            'class_of_vehicle': r'Class of Vehicie\s+([A-Z\s,]+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text_output)
            if match:
                extracted_data[key] = match.group(1)

        print("Extracted structured data:", extracted_data)  # Debug: extracted data

        # Reset file pointer to upload the file to Firebase Storage
        file.seek(0)
        blob = storage.bucket().blob(f"uploads/{file.filename}")
        blob.upload_from_file(file)
        print("File uploaded to Firebase successfully")  # Debug: successful upload

        # Mock document ID (replace with actual DB logic)
        document_id = "123456789"

        # Return structured data along with document ID
        return jsonify({
            'message': 'File uploaded and data extracted successfully!', 
            'document_id': document_id,
            'extracted_data': extracted_data
        }), 200

    except Exception as e:
        print(f"An error occurred: {e}")  # Debug: print exception
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)