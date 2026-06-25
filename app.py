from flask import Flask, render_template, request,jsonify

app = Flask(__name__)


@app.route("/")
def home():
    # 1. Check if the website is behind a reverse proxy (Nginx, Heroku, Cloudflare, etc.)
    if request.headers.getlist("X-Forwarded-For"):
        # The first IP in this list is the actual user's client IP
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        # Fallback to direct connection IP if no proxy is used
        user_ip = request.remote_addr

    # Handle local testing environments
    if user_ip == "127.0.0.1" or user_ip == "::1":
        ip_status = "Localhost (You are testing locally)"
    else:
        ip_status = "Public IP"

    # Pass the IP address into the HTML template
    return render_template("index.html", ip=user_ip, status=ip_status)

@app.route("/ping", methods=["POST"])
def ping():
    # 1. Grab data sent from the PC (JSON format)
    client_data = request.get_json()

    # Look for a key named 'message'
    user_message = client_data.get("message", "No message sent")
    print(f"Received from PC: {user_message}")

    # 2. Send back a response message to the PC
    response_data = {
        "status": "success",
        "server_message": f"Server received your message: '{user_message}'",
    }

    return jsonify(response_data)

if __name__ == "__main__":
    # Run the server locally on port 5000
    app.run(debug=True, host="0.0.0.0", port=5000)