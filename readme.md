# Personalized Learning Coach

A Django-based application that provides personalized learning experiences through interactive chats, quizzes, and goal tracking.

## Features

- Interactive chat interface with AI assistance
- Quiz system with customizable questions
- Goal tracking and progress monitoring
- Document management for learning materials
- Vector-based search capabilities

## Prerequisites

- Python 3.x
- Django
- Additional dependencies listed in `requirements.txt`

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
4. Run the development server:
   ```bash
   python manage.py runserver
   ```

## Project Structure

- `chat_backend/`: Core application logic and models
- `documents/`: Learning materials storage
- `media/`: User-uploaded content
- `personalized_learning_coach/`: Project configuration

## License

[Your License Here]
