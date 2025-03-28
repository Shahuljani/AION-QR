from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import os
import qrcode
import zipfile
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, static_folder="../frontend")
CORS(app)

# Initialize Firebase
cred_path = os.path.join(os.path.dirname(__file__), "firebase_credentials.json")
if not firebase_admin._apps:  # Prevent duplicate initialization
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/generate_qr", methods=["GET"])
def generate_qr():
    output_dir = "qr_codes"
    os.makedirs(output_dir, exist_ok=True)

    students = db.collection("studentsAIML").stream()

    for student in students:
        student_id = student.id.strip().upper()
        qr_url = f"http://127.0.0.1:5000/check?student_id={student_id}"
        qr = qrcode.make(qr_url).convert("RGB")

        # Create a new image with space for text
        qr_size = qr.size
        img = Image.new("RGB", (qr_size[0], qr_size[1] + 50), "white")
        img.paste(qr, (0, 0))

        # Add roll number text below QR code
        draw = ImageDraw.Draw(img)
        font_path = "arial.ttf"  
        try:
            font = ImageFont.truetype(font_path, 20)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), student_id, font=font)
        text_width = bbox[2] - bbox[0]
        text_position = ((qr_size[0] - text_width) // 2, qr_size[1] + 10)
        draw.text(text_position, student_id, fill="black", font=font)

        # Save QR image
        qr_path = os.path.join(output_dir, f"{student_id}.png")
        img.save(qr_path)

    # Create a ZIP file of all QR codes
    zip_file_path = os.path.join(os.getcwd(), "qr_codes.zip")
    with zipfile.ZipFile(zip_file_path, "w") as zipf:
        for file_name in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file_name)
            zipf.write(file_path, os.path.basename(file_path))

    return send_file(zip_file_path, as_attachment=True, mimetype="application/zip")

@app.route("/check", methods=["GET"])
def check_redemptions():
    student_id = request.args.get("student_id").strip().upper()
    student_ref = db.collection("studentsAIML").document(student_id)
    student = student_ref.get()

    if student.exists:
        return jsonify({
            "student_id": student_id,
            "ice_cream": student.to_dict().get("ICE CREAM", 0)
        })
    else:
        return jsonify({"error": "Student not found"}), 404

@app.route("/redeem", methods=["POST"])
def redeem():
    data = request.json
    student_id = data.get("student_id").strip().upper()

    student_ref = db.collection("studentsAIML").document(student_id)
    student = student_ref.get()

    if student.exists:
        student_data = student.to_dict()
        if student_data.get("ICE CREAM", 0) > 0:
            student_ref.update({"ICE CREAM": student_data["ICE CREAM"] - 1})
            return jsonify({"message": "Ice cream redeemed successfully!"})
        else:
            return jsonify({"error": "No more ice cream redemptions left."}), 400
    else:
        return jsonify({"error": "Student not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
