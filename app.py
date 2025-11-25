from flask import Flask 
from flask_cors import CORS
from dotenv import load_dotenv
import os
from routes.font_router import font_bp
load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/ec2-user/Chowol_Backend_Python/stoked-champion-477005-p3-3051b6933c4f.json"

from routes.translate_router import translate_bp 
from routes.inpaint_router import inpaint_bp
from routes.reinsert_router import reinsert_bp
from routes.ocr_router import ocr_bp

print("S3_BUCKET =", os.getenv("S3_BUCKET"))

app = Flask(__name__) 

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",
                "http://localhost:5174"
            ]
        }
    }
)

app.register_blueprint(translate_bp) 
app.register_blueprint(inpaint_bp)
app.register_blueprint(reinsert_bp)
app.register_blueprint(ocr_bp, url_prefix="/api/ocr")
app.register_blueprint(font_bp, url_prefix="/api/font-recommend")



@app.route("/") 
def home(): 
  return "Flask running" 

if __name__ == "__main__":
   app.run(port=5001, host="0.0.0.0")


# def create_app():
#     app = Flask(__name__)
#     app.register_blueprint(translate_bp)
#     return app

# if __name__ == "__main__":
#     app = create_app()
#     app.run(host="0.0.0.0", port=5001, debug=True)