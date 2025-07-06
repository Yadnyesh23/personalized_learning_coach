# Quiz API Documentation

This document provides comprehensive documentation for all quiz-related endpoints in the Personalized Learning Coach API.

## Table of Contents

1. [Quiz Management](#quiz-management)
2. [Question Management](#question-management)
3. [Quiz Attempts & Scoring](#quiz-attempts--scoring)
4. [Quiz Generation](#quiz-generation)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Examples](#examples)

---

## Quiz Management

### 1. Create Quiz
**Endpoint:** `POST /session/{session_id}/quiz/create/`

Creates a new quiz for a specific session.

**Request Body:**
```json
{
    "title": "Machine Learning Basics",
    "description": "Test your knowledge of fundamental ML concepts"
}
```

**Response (201 Created):**
```json
{
    "message": "Quiz created successfully",
    "quiz_id": 123
}
```

**Error Responses:**
- `404`: Invalid session ID
- `400`: Missing quiz title

### 2. Get Quiz Details
**Endpoint:** `GET /quiz/{quiz_id}/`

Retrieves detailed information about a specific quiz including all questions.

**Response (200 OK):**
```json
{
    "quiz_id": 123,
    "session_id": 456,
    "title": "Machine Learning Basics",
    "description": "Test your knowledge of fundamental ML concepts",
    "created_at": "2024-01-15T10:30:00Z",
    "questions": [
        {
            "id": 1,
            "question_text": "What is supervised learning?",
            "options": ["Learning with labeled data", "Learning without data", "Learning with unlabeled data", "Learning with test data"]
        },
        {
            "id": 2,
            "question_text": "Which algorithm is used for classification?",
            "options": ["Linear Regression", "Logistic Regression", "K-means", "Principal Component Analysis"]
        }
    ]
}
```

**Error Responses:**
- `404`: Quiz not found

### 3. List Session Quizzes
**Endpoint:** `GET /session/{session_id}/quizzes/`

Retrieves all quizzes for a specific session.

**Response (200 OK):**
```json
{
    "quizzes": [
        {
            "id": 123,
            "title": "Machine Learning Basics",
            "description": "Test your knowledge of fundamental ML concepts",
            "created_at": "2024-01-15T10:30:00Z"
        },
        {
            "id": 124,
            "title": "Neural Networks",
            "description": "Advanced neural network concepts",
            "created_at": "2024-01-16T14:20:00Z"
        }
    ]
}
```

**Error Responses:**
- `404`: Invalid session ID

### 4. List All Quizzes
**Endpoint:** `GET /quizzes/`

Retrieves all quizzes across all sessions with pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 10, max: 100)

**Response (200 OK):**
```json
{
    "count": 25,
    "next": "http://api.example.com/quizzes/?page=2",
    "previous": null,
    "results": [
        {
            "id": 123,
            "title": "Machine Learning Basics",
            "description": "Test your knowledge of fundamental ML concepts",
            "session_id": 456,
            "created_at": "2024-01-15T10:30:00Z",
            "question_count": 5,
            "linked_message_id": 789
        }
    ]
}
```

---

## Question Management

### 5. Add Questions to Quiz
**Endpoint:** `POST /quiz/{quiz_id}/questions/add/`

Adds multiple questions to an existing quiz. Supports multiple choice questions with options.

**Request Body:**
```json
{
    "questions": [
        {
            "question_text": "What is supervised learning?",
            "options": ["Learning with labeled data", "Learning without data", "Learning with unlabeled data", "Learning with test data"],
            "correct_answer": "Learning with labeled data"
        },
        {
            "question_text": "Which algorithm is used for classification?",
            "options": ["Linear Regression", "Logistic Regression", "K-means", "Principal Component Analysis"],
            "correct_answer": "Logistic Regression"
        }
    ]
}
```

**Response (201 Created):**
```json
{
    "message": "Questions added successfully",
    "questions": [
        {
            "id": 1,
            "question_text": "What is supervised learning?",
            "options": ["Learning with labeled data", "Learning without data", "Learning with unlabeled data", "Learning with test data"]
        },
        {
            "id": 2,
            "question_text": "Which algorithm is used for classification?",
            "options": ["Linear Regression", "Logistic Regression", "K-means", "Principal Component Analysis"]
        }
    ]
}
```

**Error Responses:**
- `404`: Invalid quiz ID
- `400`: Invalid questions format or missing question text

**Notes:**
- The `options` field is optional and should be an array of strings for multiple choice questions
- If no options are provided, the question will be treated as a text-based question
- The `correct_answer` should match one of the options exactly (case-sensitive)

---

## Quiz Attempts & Scoring

### 6. Submit Quiz Answers
**Endpoint:** `POST /quiz/{quiz_id}/submit/`

Submits answers for a quiz and receives immediate scoring feedback with correct answers.

**Request Body:**
```json
{
    "answers": [
        {
            "question_id": 1,
            "user_answer": "Learning with labeled data"
        },
        {
            "question_id": 2,
            "user_answer": "Logistic Regression"
        }
    ]
}
```

**Response (201 Created):**
```json
{
    "message": "Quiz answers submitted",
    "results": [
        {
            "question_id": 1,
            "question_text": "What is supervised learning?",
            "options": ["Learning with labeled data", "Learning without data", "Learning with unlabeled data", "Learning with test data"],
            "user_answer": "Learning with labeled data",
            "correct_answer": "Learning with labeled data",
            "is_correct": true,
            "attempt_id": 456
        },
        {
            "question_id": 2,
            "question_text": "Which algorithm is used for classification?",
            "options": ["Linear Regression", "Logistic Regression", "K-means", "Principal Component Analysis"],
            "user_answer": "Logistic Regression",
            "correct_answer": "Logistic Regression",
            "is_correct": true,
            "attempt_id": 457
        }
    ]
}
```

**Error Responses:**
- `404`: Invalid quiz ID
- `400`: Invalid answers format or question not found in quiz

**Notes:**
- The response includes complete question details including options and correct answers
- The `is_correct` field indicates if the user's answer matches the correct answer
- The session is automatically determined from the quiz's session

### 7. View Quiz Attempts
**Endpoint:** `GET /session/{session_id}/quiz_attempts/`

Retrieves all quiz attempts for a session with optional filtering by quiz.

**Query Parameters:**
- `quiz_id` (optional): Filter attempts by specific quiz ID

**Response (200 OK):**
```json
{
    "attempts": [
        {
            "id": 456,
            "quiz__id": 123,
            "quiz__title": "Machine Learning Basics",
            "question__id": 1,
            "question__question_text": "What is supervised learning?",
            "user_answer": "Learning with labeled training data",
            "is_correct": true,
            "attempted_at": "2024-01-15T11:00:00Z"
        },
        {
            "id": 457,
            "quiz__id": 123,
            "quiz__title": "Machine Learning Basics",
            "question__id": 2,
            "question__question_text": "Which algorithm is used for classification?",
            "user_answer": "Logistic Regression",
            "is_correct": true,
            "attempted_at": "2024-01-15T11:00:00Z"
        }
    ]
}
```

**Error Responses:**
- `404`: Invalid session ID

---

## Quiz Generation

### 8. Generate Quiz from Message
**Endpoint:** `POST /message/{message_id}/generate-quiz/`

Automatically generates a quiz based on the content of a specific chat message using AI.

**Response (201 Created):**
```json
{
    "message": "Quiz generated successfully",
    "quiz_id": 125,
    "title": "Neural Network Fundamentals Quiz",
    "description": "Test your understanding of neural network concepts discussed in the conversation",
    "questions": [
        {
            "id": 6,
            "question_text": "What is the primary function of an activation function in a neural network?",
            "options": [
                "To increase the number of neurons",
                "To introduce non-linearity into the network",
                "To reduce computational complexity",
                "To store training data"
            ],
            "correct_answer": "To introduce non-linearity into the network"
        }
    ]
}
```

**Error Responses:**
- `404`: Message not found
- `400`: Quiz already exists for this message
- `500`: Failed to generate quiz

---

## Data Models

### Quiz Model
```python
class Quiz(models.Model):
    title = models.CharField(max_length=255)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='quizzes')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Question Model
```python
class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    correct_answer = models.TextField(blank=True)
    options = models.JSONField(default=list, blank=True)  # Multiple choice options
```

### UserQuizAttempt Model
```python
class UserQuizAttempt(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers')
    user_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True)  # Null for ungraded, True/False after checking
    attempted_at = models.DateTimeField(auto_now_add=True)
```

---

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
    "error": "Quiz title is required"
}
```

**404 Not Found:**
```json
{
    "error": "Invalid session ID"
}
```

**500 Internal Server Error:**
```json
{
    "error": "Failed to generate quiz: AI service unavailable"
}
```

### Error Codes Summary
- `400`: Bad Request (missing required fields, invalid data format)
- `404`: Not Found (invalid IDs, resources don't exist)
- `500`: Internal Server Error (server-side processing errors)

---

## Examples

### Complete Quiz Workflow

1. **Create a Session:**
```bash
POST /session/create/
Response: {"session_id": 456}
```

2. **Create a Quiz:**
```bash
POST /session/456/quiz/create/
{
    "title": "Python Programming Basics",
    "description": "Test your Python knowledge"
}
Response: {"message": "Quiz created successfully", "quiz_id": 123}
```

3. **Add Questions:**
```bash
POST /quiz/123/questions/add/
{
    "questions": [
        {
            "question_text": "What is the output of print(2 + 2)?",
            "options": ["2", "4", "6", "8"],
            "correct_answer": "4"
        },
        {
            "question_text": "Which data type is used for text in Python?",
            "options": ["int", "str", "float", "bool"],
            "correct_answer": "str"
        }
    ]
}
```

4. **Submit Answers:**
```bash
POST /quiz/123/submit/
{
    "answers": [
        {
            "question_id": 1,
            "user_answer": "4"
        },
        {
            "question_id": 2,
            "user_answer": "str"
        }
    ]
}

Response:
{
    "message": "Quiz answers submitted",
    "results": [
        {
            "question_id": 1,
            "question_text": "What is the output of print(2 + 2)?",
            "options": ["2", "4", "6", "8"],
            "user_answer": "4",
            "correct_answer": "4",
            "is_correct": true,
            "attempt_id": 456
        },
        {
            "question_id": 2,
            "question_text": "Which data type is used for text in Python?",
            "options": ["int", "str", "float", "bool"],
            "user_answer": "str",
            "correct_answer": "str",
            "is_correct": true,
            "attempt_id": 457
        }
    ]
}
```

5. **View Results:**
```bash
GET /session/456/quiz_attempts/?quiz_id=123
```

### AI-Generated Quiz Example

**Generate Quiz from Message:**
```bash
POST /message/789/generate-quiz/
Response: {
    "message": "Quiz generated successfully",
    "quiz_id": 124,
    "title": "Machine Learning Concepts Quiz",
    "description": "Based on our discussion about ML fundamentals",
    "questions": [
        {
            "id": 3,
            "question_text": "What is the difference between supervised and unsupervised learning?",
            "options": ["Data labeling", "Algorithm complexity", "Training time", "Model size"],
            "correct_answer": "Data labeling"
        }
    ]
}
```

---

## Best Practices

1. **Quiz Creation:**
   - Always provide descriptive titles and descriptions
   - Use clear, unambiguous question text
   - For multiple choice questions, provide 4 distinct options
   - Ensure correct answers match one of the options exactly (case-sensitive)
   - Make all options plausible to avoid obvious answers

2. **Answer Submission:**
   - Submit all answers for a quiz at once
   - Use exact text matching for correct answers
   - Handle case sensitivity appropriately

3. **Error Handling:**
   - Always check for 404 errors when using IDs
   - Validate request body format before submission
   - Handle AI generation failures gracefully

4. **Performance:**
   - Use pagination for large quiz lists
   - Filter attempts by quiz_id when needed
   - Cache frequently accessed quiz data

---

## Rate Limits & Security

- No specific rate limits are currently implemented
- All endpoints require valid session IDs
- Quiz attempts are tied to specific sessions for data isolation
- AI-generated quizzes are linked to specific messages for context

---

*Last Updated: January 2024*
*API Version: 1.0*