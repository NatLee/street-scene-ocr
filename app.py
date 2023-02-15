import io
import base64
import numpy as np

from flask import Flask, flash, request, redirect, render_template

from PIL import ImageFont, ImageDraw, Image
import cv2

import easyocr

READER = easyocr.Reader(['ch_tra','en'])

FONT_PATH = './font/Noto.otf'
FONT = ImageFont.truetype(FONT_PATH, 20)

UPLOAD_FOLDER = './static/uploads/'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

DEFAULT_FILE_NAME = 'sample'
RESULT_FILE_NAME = 'result.png'

app = Flask(__name__)
app.secret_key = 'YEE'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def image_to_base64(img:np.ndarray):
    img = Image.fromarray(img.astype("uint8"))
    raw_bytes = io.BytesIO()
    img.save(raw_bytes, "PNG")
    raw_bytes.seek(0)
    img_base64 = base64.b64encode(raw_bytes.getvalue()).decode('ascii')
    mime = "image/png"
    uri = "data:%s;base64,%s"%(mime, img_base64)
    return uri

def draw_text_on_image(img, x, y, text, text_color):
    img_pil = Image.fromarray(img)
    draw = ImageDraw.Draw(img_pil)
    draw.text((x, y), text, font=FONT, fill=text_color)
    img = np.array(img_pil)
    return img


@app.route('/')
def upload_form():
    return render_template('upload.html')

@app.route('/', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No image selected for uploading')
        return redirect(request.url)

    if file and allowed_file(file.filename):

        # load image from memory
        filestr = request.files['file'].read()
        npimg = np.frombuffer(filestr, np.uint8)
        original_image = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        original_image = cv2.cvtColor(original_image , cv2.COLOR_BGR2RGB)

        # OCR
        ocr_result = READER.readtext(original_image)
        ocr_result = sorted(ocr_result, key=lambda x: x[-1])

        result_image = original_image.copy()

        # ----------------------------------------
        # draw rectangle and text
        for position, text, percent in ocr_result:
            x1y1, _, x2y2, _= position
            x1, y1 = x1y1
            x2, y2 = x2y2

            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            if percent > 0.3:
                rectangle_color = (50, 255, 50)
                text_color = (50, 255, 50, 0) # bgra
            else:
                rectangle_color = (50, 50, 255)
                text_color = (50, 50, 255, 0)

            result_image = cv2.rectangle(result_image, (x1, y1), (x2, y2), color=rectangle_color, thickness=2)

            # ----------------------------------------

            # draw text
            text = f'{text} {percent*100:.02f}%'
            result_image = draw_text_on_image(result_image, x1, y2, text, text_color)

        # ----------------------------------------

        # return image(base64)
        result_image_uri = image_to_base64(result_image)
        original_image_uri = image_to_base64(original_image)

        return render_template('upload.html', ocr_result=ocr_result, original_image=original_image_uri, result_image=result_image_uri)

    else:
        flash('Allowed image types are -> png, jpg, jpeg')
        return redirect(request.url)


if __name__ == "__main__":

    app.run(
        port=80,
        host='0.0.0.0',
        debug=True
    )

