from flask import Flask, render_template, request, send_file, send_from_directory
from PIL import Image
import pdfplumber
from docx import Document
import fitz 
import subprocess
import uuid
import os
import time
import threading
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
from datetime import datetime
import zipfile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import flash

app = Flask(__name__)
app.secret_key = "super_secret_key_for_unitools"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FILE_EXPIRY_SECONDS = 15 * 60  # 15 minutes


def cleanup_uploads():
    while True:
        now = time.time()

        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)

            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)

                if file_age > FILE_EXPIRY_SECONDS:
                    try:
                        os.remove(file_path)
                        print(f"Deleted expired file: {filename}")
                    except Exception as e:
                        print(f"Error deleting {filename}: {e}")

        time.sleep(300)  # run every 5 minutes

# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")


# ================= CATEGORY PAGES =================

@app.route("/pdf-tools")
def pdf_tools():
    return render_template("pdf/tools.html")


@app.route("/image-tools")
def image_tools():
    return render_template("image/image_tools.html")


# ================= PDF → WORD =================

@app.route("/pdf-to-word", methods=["GET", "POST"])
def pdf_to_word():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
        pdf_file.save(input_path)

        doc = Document()
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    doc.add_paragraph(text)

        output_path = input_path.replace(".pdf", ".docx")
        doc.save(output_path)
        return send_file(output_path, as_attachment=True)

    return render_template("pdf/pdf_to_word.html")


# ================= PDF → JPG (ALL PAGES) =================

@app.route("/pdf-to-jpg", methods=["GET", "POST"])
def pdf_to_jpg():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        unique_id = uuid.uuid4()
        input_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}.pdf")
        pdf_file.save(input_path)

        doc = fitz.open(input_path)
        image_paths = []

        # Loop through EVERY page
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)  # High DPI for better quality
            img_filename = f"{unique_id}_page_{i+1}.jpg"
            img_path = os.path.join(UPLOAD_FOLDER, img_filename)
            pix.save(img_path)
            image_paths.append(img_path)
        
        doc.close()

        # If only 1 page, just download that image
        if len(image_paths) == 1:
            return send_file(image_paths[0], as_attachment=True)

        # If multiple pages, create a ZIP file
        zip_filename = f"{unique_id}_images.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in image_paths:
                zipf.write(file, os.path.basename(file))

        return send_file(zip_path, as_attachment=True)

    return render_template("pdf/pdf_to_jpg.html")


# ================= JPG → PDF =================

@app.route("/jpg-to-pdf", methods=["GET", "POST"])
def jpg_to_pdf():
    if request.method == "POST":
        image_file = request.files["image_file"]
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.jpg")
        image_file.save(input_path)

        image = Image.open(input_path).convert("RGB")
        output_path = input_path.replace(".jpg", ".pdf")
        image.save(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/jpg_to_pdf.html")

# ================= MERGE PDF =================

@app.route("/merge-pdf", methods=["GET", "POST"])
def merge_pdf():
    if request.method == "POST":
        pdf_files = request.files.getlist("pdf_files")
        
        if not pdf_files or pdf_files[0].filename == '':
            return "No files selected", 400

        doc_merged = fitz.open()
        
        # Sort files by name if needed, or keep selection order
        for pdf in pdf_files:
            # Save temp file to process
            temp_filename = f"{uuid.uuid4()}_{pdf.filename}"
            temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
            pdf.save(temp_path)
            
            # Open and append to master doc
            with fitz.open(temp_path) as doc:
                doc_merged.insert_pdf(doc)

        output_filename = f"merged_{uuid.uuid4()}.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        doc_merged.save(output_path)
        doc_merged.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/merge_pdf.html")


# ================= COMPRESS PDF =================

@app.route("/compress-pdf", methods=["GET", "POST"])
def compress_pdf():
    if request.method == "POST":
        file = request.files.get("pdf_file")
        target_mb = request.form.get("target_mb")
        
        # Default to 2.0 MB if user leaves it blank
        target_mb = float(target_mb) if target_mb else 2.0
        
        if file:
            # 1. Save the original file
            input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{file.filename}")
            file.save(input_path)
            output_path = os.path.join(UPLOAD_FOLDER, f"compressed_{uuid.uuid4()}.pdf")

            # 2. Open and Compress
            doc = fitz.open(input_path)
            
            # Optimization strategy: garbage=4 removes duplicates, deflate shrinks streams
            doc.save(output_path, garbage=4, deflate=True, clean=True)
            doc.close()

            # 3. Analyze Results
            original_size = os.path.getsize(input_path)
            compressed_size = os.path.getsize(output_path)
            
            # 4. Logical Comparison Gate
            if compressed_size < original_size:
                # Calculate how much space was saved
                savings_pct = round(((original_size - compressed_size) / original_size) * 100, 1)
                
                # If we successfully hit the user's target or improved it significantly
                flash(f"Success! Reduced by {savings_pct}% to {round(compressed_size/1024, 1)} KB.", "success")
                return send_file(output_path, as_attachment=True, download_name=f"compressed_{file.filename}")
            
            else:
                # If file grew, we ignore the output and send the original
                flash("Note: Your file was already highly optimized. No further reduction possible.", "info")
                return send_file(input_path, as_attachment=True, download_name=f"original_{file.filename}")
            
    return render_template("pdf/compress_pdf.html")


# ================= WORD → PDF =================

@app.route("/word-to-pdf", methods=["GET", "POST"])
def word_to_pdf():
    if request.method == "POST":
        word_file = request.files["word_file"]
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.docx")
        word_file.save(input_path)

        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                input_path,
                "--outdir",
                UPLOAD_FOLDER,
            ]
        )

        output_path = input_path.replace(".docx", ".pdf")
        return send_file(output_path, as_attachment=True)

    return render_template("pdf/word_to_pdf.html")


# ================= PROTECT PDF =================

@app.route("/protect-pdf", methods=["GET", "POST"])
def protect_pdf():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        password = request.form["password"]

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
        pdf_file.save(input_path)
        output_path = input_path.replace(".pdf", "_protected.pdf")

        doc = fitz.open(input_path)
        doc.save(
            output_path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw=password,
            user_pw=password,
            permissions=fitz.PDF_PERM_PRINT,
        )
        doc.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/protect_pdf.html")


# ================= UNLOCK PDF =================

@app.route("/unlock-pdf", methods=["GET", "POST"])
def unlock_pdf():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        password = request.form["password"]

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
        pdf_file.save(input_path)
        output_path = input_path.replace(".pdf", "_unlocked.pdf")

        doc = fitz.open(input_path)
        if not doc.authenticate(password):
            return "Incorrect password", 401

        doc.save(output_path)
        doc.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/unlock_pdf.html")


# ================= DELETE PDF PAGES =================

@app.route("/delete-pdf-pages", methods=["GET", "POST"])
def delete_pdf_pages():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        pages_input = request.form["pages"]

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
        pdf_file.save(input_path)
        output_path = input_path.replace(".pdf", "_pages_deleted.pdf")

        doc = fitz.open(input_path)
        pages = set()

        for part in pages_input.split(","):
            if "-" in part:
                a, b = map(int, part.split("-"))
                pages.update(range(a - 1, b))
            else:
                pages.add(int(part) - 1)

        for p in sorted(pages, reverse=True):
            if 0 <= p < doc.page_count:
                doc.delete_page(p)

        doc.save(output_path)
        doc.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/delete_pdf_pages.html")


# ================= ADD PAGE NUMBERS =================

def to_roman(num):
    roman_map = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    result = ""
    for value, symbol in roman_map:
        while num >= value:
            result += symbol
            num -= value
    return result


@app.route("/add-page-numbers", methods=["GET", "POST"])
def add_page_numbers():
    if request.method == "POST":
        pdf_file = request.files["pdf_file"]
        position = request.form.get("position", "bottom-center")
        style = request.form.get("style", "decimal")
        range_start = request.form.get("range_start")
        range_end = request.form.get("range_end")
        range_style = request.form.get("range_style", "roman-lower")

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
        pdf_file.save(input_path)
        output_path = input_path.replace(".pdf", "_numbered.pdf")

        doc = fitz.open(input_path)

        try:
            range_start = int(range_start) if range_start else None
            range_end = int(range_end) if range_end else None
        except ValueError:
            range_start = range_end = None

        for i, page in enumerate(doc):
            page_num = i + 1
            use_style = style

            if range_start and range_end and range_start <= page_num <= range_end:
                use_style = range_style

            if use_style == "roman-lower":
                text = to_roman(page_num).lower()
            elif use_style == "roman-upper":
                text = to_roman(page_num)
            else:
                text = str(page_num)

            w, h = page.rect.width, page.rect.height

            if position == "bottom-right":
                x, y = w - 40, h - 30
            elif position == "bottom-left":
                x, y = 20, h - 30
            else:
                x, y = w / 2 - 10, h - 30

            page.insert_text((x, y), text, fontsize=12, color=(0, 0, 0))

        doc.save(output_path)
        doc.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf/add_page_numbers.html")


# ================= SERVER UPLOADS =================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ================= IMAGE / AI =================

# ================= ADD IMAGE BORDER =================

@app.route('/image-border', methods=['GET', 'POST'])
def image_border():
    if request.method == 'POST':
        image_file = request.files['image_file']
        border_size = int(request.form.get('border_size', 20))
        border_color = request.form.get('border_color', '#ffffff')

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.png")
        image_file.save(input_path)

        img = Image.open(input_path)

        # Convert hex to RGB
        border_color = border_color.lstrip('#')
        border_rgb = tuple(int(border_color[i:i+2], 16) for i in (0, 2, 4))

        # Add border
        bordered_img = Image.new(
            "RGB",
            (img.width + border_size * 2, img.height + border_size * 2),
            border_rgb
        )
        bordered_img.paste(img, (border_size, border_size))

        output_path = input_path.replace(".png", "_bordered.png")
        bordered_img.save(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template('image/image_border.html')

# ================= RESIZE IMAGE =================

@app.route('/resize-image', methods=['GET', 'POST'])
def resize_image():
    if request.method == 'POST':
        image_file = request.files['image_file']
        width = int(request.form.get('width'))
        height = int(request.form.get('height'))

        ext = os.path.splitext(image_file.filename)[1].lower()
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}{ext}")
        image_file.save(input_path)

        img = Image.open(input_path)
        # Resizing the image
        resized_img = img.resize((width, height), Image.Resampling.LANCZOS)

        output_path = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}{ext}")
        resized_img.save(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template('image/resize_image.html')

# ================= COMPRESS IMAGE =================

@app.route('/compress-image', methods=['GET', 'POST'])
def compress_image():
    if request.method == 'POST':
        image_file = request.files['image_file']
        quality = request.form.get('quality', 'medium')

        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            return "Only JPG and PNG supported", 400

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}{ext}")
        image_file.save(input_path)

        output_path = input_path.replace(ext, f"_compressed{ext}")

        img = Image.open(input_path)

        if quality == "low":
            q = 30
        elif quality == "high":
            q = 85
        else:
            q = 60  # medium

        if ext in ['.jpg', '.jpeg']:
            img.save(output_path, optimize=True, quality=q)
        else:
            img.save(output_path, optimize=True)

        return send_file(output_path, as_attachment=True)

    return render_template('image/compress_image.html')

# ================= PNG → JPG =================

@app.route('/png-to-jpg', methods=['GET', 'POST'])
def png_to_jpg():
    if request.method == 'POST':
        image_file = request.files['image_file']
        quality = int(request.form.get('quality', 85))

        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.png")
        image_file.save(input_path)

        img = Image.open(input_path)

        # Convert to RGB (important for JPG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output_path = input_path.replace(".png", ".jpg")
        img.save(output_path, "JPEG", quality=quality)

        return send_file(output_path, as_attachment=True)

    return render_template('image/png_to_jpg.html')

# ================= JPG → PNG =================

@app.route('/jpg-to-png', methods=['GET', 'POST'])
def jpg_to_png():
    if request.method == 'POST':
        image_file = request.files['image_file']

        ext = image_file.filename.split('.')[-1].lower()
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.{ext}")
        image_file.save(input_path)

        img = Image.open(input_path)

        output_path = input_path.replace(".jpg", ".png")
        img.save(output_path, "PNG")

        return send_file(output_path, as_attachment=True)

    return render_template('image/jpg_to_png.html')

# ================= AI TOOLS =================
@app.route("/ai-tools")
def ai_tools():
    return render_template("ai/ai_tools.html")

# ================= AI RESUME MATCHER =================

@app.route('/ai-resume-matcher', methods=['GET', 'POST'])
def resume_matcher():
    score = None
    if request.method == 'POST':
        job_desc = request.form.get('job_description')
        resume_text = request.form.get('resume_text')

        if job_desc and resume_text:
            # Vectorize the text to compare keywords
            content = [job_desc, resume_text]
            cv = TfidfVectorizer()
            matrix = cv.fit_transform(content)
            
            # Calculate Similarity
            similarity_matrix = cosine_similarity(matrix)
            # Get the percentage match
            match_percentage = similarity_matrix[0][1] * 100
            score = round(match_percentage, 2)

    return render_template('ai/resume_matcher.html', score=score)




# ================= CHART TOOLS =================
@app.route('/chart-tools')
def chart_tools():
    return render_template('charts/charts_tools.html')



# ================= GANTT CHART =================



@app.route('/gantt-chart', methods=['GET', 'POST'])
def gantt_chart():
    if request.method == 'POST':
        tasks = request.form.getlist('task[]')
        starts = request.form.getlist('start[]')
        ends = request.form.getlist('end[]')

        fig, ax = plt.subplots(figsize=(10, 5))

        for i in range(len(tasks)):
            start_date = datetime.strptime(starts[i], "%Y-%m-%d")
            end_date = datetime.strptime(ends[i], "%Y-%m-%d")
            duration = (end_date - start_date).days

            ax.barh(tasks[i], duration, left=start_date)

        ax.set_xlabel("Date")
        ax.set_ylabel("Tasks")
        plt.xticks(rotation=45)
        plt.tight_layout()

        output_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_gantt.png")
        plt.savefig(output_path)
        plt.close()

        return send_file(output_path, as_attachment=True)

    return render_template("charts/gantt_chart.html")

# ================= PIE CHART =================

@app.route('/pie-chart', methods=['GET', 'POST'])
def pie_chart():
    if request.method == 'POST':
        # Get data from the form
        labels = request.form.getlist('labels[]')
        values = request.form.getlist('values[]')

        # Filter out empty entries
        data = [(l, float(v)) for l, v in zip(labels, values) if l.strip() and v]

        if not data:
            return "Please provide valid data for the chart.", 400

        # Unzip back into lists
        clean_labels, clean_values = zip(*data)

        # Create the chart
        plt.figure(figsize=(8, 6))
        plt.pie(clean_values, labels=clean_labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.title("Generated Pie Chart")

        # Save the file
        output_filename = f"{uuid.uuid4()}_pie.png"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        plt.savefig(output_path, bbox_inches='tight')
        plt.close()

        return send_file(output_path, as_attachment=True)

    return render_template('charts/pie_chart.html') 



# ================= RUN =================

if __name__ == "__main__":
    # Start the cleanup thread here, just before the app starts
    cleanup_thread = threading.Thread(target=cleanup_uploads, daemon=True)
    cleanup_thread.start()

    app.run(host='0.0.0.0', port=5000, debug=True)