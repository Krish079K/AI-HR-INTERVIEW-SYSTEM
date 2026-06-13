from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, decode_token
import json
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
jwt = JWTManager(app)

with app.app_context():
    # Test JSON-serialized string identity
    identity_dict = {"id": 1, "email": "admin@interview.ai", "role": "admin"}
    identity_str = json.dumps(identity_dict)
    
    token = create_access_token(identity=identity_str)
    print("Generated Token:", token)
    
    try:
        decoded = decode_token(token)
        print("Decoded successfully:", decoded)
        
        # Verify we can load the dictionary back
        loaded_identity = json.loads(decoded['sub'])
        print("Loaded identity matches original dict:", loaded_identity == identity_dict)
    except Exception as e:
        print("Decoding failed:", e)
