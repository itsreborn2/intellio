from fastapi import Depends
from stockeasy.services.telegram.rag import TelegramRAGService
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from stockeasy.services.rag import StockeasyRAGService

def get_stockeasy_rag_service() -> StockeasyRAGService:
    return StockeasyRAGService()

def get_telegram_rag_service() -> TelegramRAGService:
    return TelegramRAGService()

def get_question_classifier() -> QuestionClassifierService:
    return QuestionClassifierService() 