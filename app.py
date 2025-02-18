import os
import base64
import PyPDF2
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

VALID_API_KEY = 'Lestibanget050899APIKey'

# Folder untuk menyimpan file yang di-upload
UPLOAD_FOLDER = 'uploads'
SELEKSI_FOLDER = 'seleksi'
GAGAL_TERSELEKSI_FOLDER = 'gagal_terseleksi'

# Membuat folder jika belum ada
os.makedirs(SELEKSI_FOLDER, exist_ok=True)
os.makedirs(GAGAL_TERSELEKSI_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SELEKSI_FOLDER'] = SELEKSI_FOLDER
app.config['GAGAL_TERSELEKSI_FOLDER'] = GAGAL_TERSELEKSI_FOLDER

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_from_base64(file_data, filename):
    try:
        # Decode base64
        file_content = base64.b64decode(file_data)
        
        # Tentukan path lengkap untuk menyimpan file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Simpan file di folder uploads
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path
    except Exception as e:
        print(f"Error decoding base64 for {filename}: {e}")
        return None
def verify_api_key(api_key):
    return api_key == VALID_API_KEY

# Fungsi untuk membuat response error ketika API Key tidak valid
def api_key_required():
    return jsonify({"status": 401, "message": "API Key is required or invalid"}), 401

# Endpoint login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    # Hardcoded username dan password
    username = "Arif Kejora"
    password = "Lestibanget050899"

    if not data or data.get("username") != username or data.get("password") != password:
        return jsonify({"status": 401, "message": "Invalid username or password"}), 401

    # Mengembalikan API Key
    return jsonify({
        "status": 200,
        "message": "login berhasil",
        "api_key": VALID_API_KEY
    }), 200

# Fungsi untuk memeriksa header API Key
def require_api_key(func):
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('API-Key')

        if not api_key or not verify_api_key(api_key):
            return api_key_required()

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


# Fungsi untuk memproses file CV
def process_cv(file_path, keywords):
    matching_keywords = 0
    found_keywords = []  # Daftar kata kunci yang ditemukan
    
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()  # Mengambil teks dari seluruh halaman

        text = text.lower()  # Mengubah teks menjadi huruf kecil

        for keyword in keywords:
            keyword = keyword.strip().lower()  # Menghapus spasi ekstra dan mengubah kata kunci menjadi huruf kecil
            if keyword in text:
                matching_keywords += 1
                found_keywords.append(keyword)

    except Exception as e:
        return 0, []  # Mengembalikan tuple dengan nilai default jika ada error

    # Menghitung persentase kecocokan
    percentage = (matching_keywords / len(keywords)) * 100
    return percentage, found_keywords


# API untuk meng-upload file

@app.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    # Memeriksa apakah request body berupa JSON
    if not request.json:
        return jsonify({"status": 400, "message": "Bad Request: No JSON data"}), 400
    
    if 'file' not in request.json:
        return jsonify({"status": 400, "message": "Bad Request: 'file' key is missing"}), 400

    files = request.json.get('file', [])
    
    if not files:
        return jsonify({"status": 400, "message": "Bad Request: No files found"}), 400

    # Lanjutkan memproses file dari JSON
    for file in files:
        file_name = file.get('file_name')
        base64_data = file.get('pdffile')
        
        if not file_name or not base64_data:
            return jsonify({"status": 400, "message": "Bad Request: Missing file_name or pdffile"}), 400
        
        file_path = save_file_from_base64(base64_data, file_name)
        if not file_path:
            return jsonify({"status": 500, "message": f"Error saving file {file_name}"}), 500

    return jsonify({"status": 200, "message": "Files uploaded successfully"}), 200


# API untuk melakukan filter berdasarkan kata kunci
@app.route('/filter', methods=['POST'])
@require_api_key
def filter_cv():
    data = request.get_json()
    if not data:
        return jsonify({"status": 400, "message": "No data provided"}), 400

    keywords = data.get('keyword', '').split(',')
    keywords = [kw.strip().lower() for kw in keywords]  # Menghapus spasi ekstra

    files = data.get('file', [])
    if not files:
        return jsonify({"status": 400, "message": "No files provided"}), 400

    result = []
    
    for file_data in files:
        filename = file_data.get('filename')
        if filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            percentage, found_keywords = process_cv(file_path, keywords)

            # Menyimpan file berdasarkan persentase kecocokan
            if percentage > 50:
                # Simpan di folder seleksi
                new_filename = f"{int(percentage)}%-{filename}"
                new_file_path = os.path.join(app.config['SELEKSI_FOLDER'], new_filename)
                os.rename(file_path, new_file_path)
            else:
                # Simpan di folder gagal terseleksi
                new_filename = f"{int(percentage)}%-{filename}"
                new_file_path = os.path.join(app.config['GAGAL_TERSELEKSI_FOLDER'], new_filename)
                os.rename(file_path, new_file_path)

            result.append({
                "filename": filename,
                "match_percentage": f"{percentage}%",
                "keyword_found": ",".join(found_keywords),
                "saved_in_folder": 'seleksi' if percentage > 50 else 'gagal_terseleksi'
            })

    return jsonify({"status": 200, "message": "Berhasil filter", "result": result}), 200


# API untuk menampilkan daftar file CV dalam folder tertentu
# API untuk menampilkan daftar file CV dalam folder tertentu
@app.route('/listcv', methods=['POST'])
@require_api_key
def list_cv():
    data = request.get_json()
    if not data:
        return jsonify({"status": 400, "message": "No data provided"}), 400

    folder_path = data.get('folder_path')
    if not folder_path:
        return jsonify({"status": 400, "message": "Folder path is required"}), 400

    # Tentukan folder berdasarkan parameter yang diberikan
    if folder_path == 'uploads':
        folder = app.config['UPLOAD_FOLDER']
    elif folder_path == 'seleksi':
        folder = app.config['SELEKSI_FOLDER']
    elif folder_path == 'gagal_terseleksi':
        folder = app.config['GAGAL_TERSELEKSI_FOLDER']
    else:
        return jsonify({"status": 400, "message": "Invalid folder path"}), 400

    # Dapatkan daftar file dalam folder yang ditentukan
    try:
        files = []
        for filename in os.listdir(folder):
            if os.path.isfile(os.path.join(folder, filename)):
                files.append({"filename": filename})

        # Jika tidak ada file ditemukan, kembalikan status 404
        if not files:
            return jsonify({
                "status": 404,
                "message": "Tidak ada CV didalam folder",
                "result": files
            }), 404
        
        return jsonify({
            "status": 200,
            "message": "List CV telah ditemukan",
            "result": files
        }), 200

    except Exception as e:
        return jsonify({"status": 500, "message": f"Error reading files: {e}"}), 500



if __name__ == '__main__':
    app.run(debug=True)
