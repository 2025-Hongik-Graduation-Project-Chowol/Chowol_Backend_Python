from flask import Flask 
from dotenv import load_dotenv
import os
load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "stoked-champion-477005-p3-3051b6933c4f.json"

from routes.translate_router import translate_bp 
from routes.inpaint_router import inpaint_bp
from routes.reinsert_router import reinsert_bp
from routes.ocr_router import ocr_bp

print("S3_BUCKET =", os.getenv("S3_BUCKET"))

app = Flask(__name__) 

app.register_blueprint(translate_bp) 
app.register_blueprint(inpaint_bp)
app.register_blueprint(reinsert_bp)
app.register_blueprint(ocr_bp, url_prefix="/api/ocr")



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