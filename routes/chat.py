from flask import Blueprint, request, jsonify
from services.llm_service import ask_llm

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    question = data.get("message")

    answer = ask_llm(question)

    return jsonify({
        "answer": answer
    })