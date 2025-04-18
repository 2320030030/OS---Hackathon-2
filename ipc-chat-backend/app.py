from flask import Flask, request, jsonify, render_template
from multiprocessing import Queue
import threading
import time
import json
import os

app = Flask(__name__)

# Queues for IPC simulation
user_to_network = Queue()
network_to_storage = Queue()

# File storage paths
MSG_FILE = "messages.json"
CONTACT_FILE = "contacts.json"

# Load stored data from files (if available)
def load_from_file(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def save_to_file(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Data stores
stored_messages = load_from_file(MSG_FILE)
contacts = load_from_file(CONTACT_FILE)

# Network handler thread
def network_handler():
    while True:
        msg_obj = user_to_network.get()
        if msg_obj == "END":
            break
        msg_obj["status"] = "sent"
        print(f"[Network] Transmitting: {msg_obj['message']}")
        time.sleep(1)
        network_to_storage.put(msg_obj)

# Storage handler thread
def storage_handler():
    while True:
        msg_obj = network_to_storage.get()
        if msg_obj == "END":
            break
        msg_obj["status"] = "delivered"
        msg_obj["stored_at"] = time.strftime("%H:%M:%S")
        print(f"[Storage] Saved: {msg_obj['message']}")
        save_to_file(stored_messages, MSG_FILE)

# Start IPC threads
threading.Thread(target=network_handler, daemon=True).start()
threading.Thread(target=storage_handler, daemon=True).start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')  # Optional front-end

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    msg = data.get('message')
    sender = data.get('sender')
    receiver = data.get('receiver')

    if msg and sender and receiver:
        msg_obj = {
            "message": msg,
            "sender": sender,
            "receiver": receiver,
            "status": "queued",
            "timestamp": time.strftime("%H:%M:%S")
        }
        stored_messages.append(msg_obj)
        save_to_file(stored_messages, MSG_FILE)
        user_to_network.put(msg_obj)
        print(f"[User] Sent: {msg}")
        return jsonify({"status": "queued", "message": msg_obj})
    return jsonify({"status": "error", "reason": "Missing message/sender/receiver"}), 400

@app.route('/messages', methods=['GET'])
def get_all_messages():
    return jsonify(stored_messages)

@app.route('/search_messages', methods=['GET'])
def search_messages():
    keyword = request.args.get('keyword', '').lower()
    time_filter = request.args.get('time')
    filtered = [msg for msg in stored_messages if 
                (keyword in msg['message'].lower()) and
                (not time_filter or msg['timestamp'] == time_filter)]
    return jsonify(filtered)

@app.route('/clear_messages', methods=['DELETE'])
def clear_messages():
    stored_messages.clear()
    save_to_file(stored_messages, MSG_FILE)
    return jsonify({"status": "cleared all messages"})

# Contact APIs
@app.route('/add_contact', methods=['POST'])
def add_contact():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    if not name or not phone:
        return jsonify({"status": "error", "reason": "Missing name or phone"}), 400

    contact = {
        "name": name,
        "phone": phone,
        "timestamp": time.strftime("%H:%M:%S")
    }
    contacts.append(contact)
    save_to_file(contacts, CONTACT_FILE)
    print(f"[Contact] Added: {name}, {phone}")
    return jsonify({"status": "contact added", "contact": contact})

@app.route('/contacts', methods=['GET'])
def get_contacts():
    return jsonify(contacts)

@app.route('/search_contacts', methods=['GET'])
def search_contacts():
    query = request.args.get('query', '').lower()
    filtered = [c for c in contacts if query in c['name'].lower() or query in c['phone']]
    return jsonify(filtered)

@app.route('/edit_contact', methods=['PUT'])
def edit_contact():
    data = request.json
    name = data.get('name')
    new_phone = data.get('new_phone')

    for contact in contacts:
        if contact['name'] == name:
            contact['phone'] = new_phone
            save_to_file(contacts, CONTACT_FILE)
            return jsonify({"status": "updated", "contact": contact})
    return jsonify({"status": "error", "reason": "Contact not found"}), 404

@app.route('/delete_contact', methods=['DELETE'])
def delete_contact():
    data = request.json
    name = data.get('name')
    global contacts
    contacts = [c for c in contacts if c['name'] != name]
    save_to_file(contacts, CONTACT_FILE)
    return jsonify({"status": "deleted", "name": name})

@app.route('/clear_contacts', methods=['DELETE'])
def clear_contacts():
    contacts.clear()
    save_to_file(contacts, CONTACT_FILE)
    return jsonify({"status": "cleared all contacts"})

if __name__ == '__main__':
    app.run(debug=True)
