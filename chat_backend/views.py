from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.pagination import PageNumberPagination

from .models import GlobalMemory, ChatSession, ChatMessage , Quiz, Question, UserQuizAttempt , Goal
from .utils.vectorstore import process_pdf_upload     

from django.conf import settings
from groq import Groq
from .utils.groq_utils import generate_streaming_assistant_response
from django.http import StreamingHttpResponse
import json
import traceback

class InitMemoryView(APIView):
    def post(self, request):
        if GlobalMemory.objects.exists():
            return Response({"error": "Memory already exists"}, status=400) 
        preferences = request.data.get("preferences", "")
        GlobalMemory.objects.create(preferences=preferences)
        return Response({"message": "Global memory initialized"}) 


class UpdateMemoryView(APIView):
    def post(self, request):
        memory = GlobalMemory.objects.first() 
        if not memory:
            return Response({"error": "Global memory not initialized. Please call /memory/init/ first."}, status=400)
        preferences = request.data.get("preferences")
        if preferences:
            memory.preferences += preferences + "\n"
        memory.save() 
        return Response({"message": "Memory updated"}) 

    def get(self, request):
        memory = GlobalMemory.objects.first() 
        if not memory:
            return Response({"error": "Global memory not initialized."}, status=400)
        return Response({"preferences": memory.preferences}) 

class CreateSessionView(APIView):
    def post(self, request):
        session = ChatSession.objects.create() 
        return Response({"session_id": session.id})


class UploadPDFView(APIView):
    parser_classes = [MultiPartParser]  

    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id) 
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        pdf_file = request.FILES.get("pdf") 
        if not pdf_file:
            return Response({"error": "No PDF file provided"}, status=400)

        # Save PDF to file system
        session.uploaded_pdf = pdf_file
        session.save() 
        
        # Process PDF and save to vector store with session_id as pdf_id
        try:
            pdf_id, chunk_count = process_pdf_upload(pdf_file, pdf_id=str(session_id))
            return Response({
                "message": "PDF uploaded and processed successfully",
                "pdf_id": pdf_id
            })
        except Exception as e:
            traceback.print_exc()
            return Response({
                "error": f"PDF upload failed: {str(e)}"
            }, status=500) 

class AddMessageView(APIView):
    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        message_content = request.data.get("message")
        is_user_message = request.data.get("is_user", True)
        quiz_id = request.data.get("quiz_id") # NEW: Get quiz_id from request

        if not message_content:
            return Response({"error": "Message content is required"}, status=400)

        quiz_instance = None
        if quiz_id:
            try:
                quiz_instance = Quiz.objects.get(id=quiz_id)
            except Quiz.DoesNotExist:
                return Response({"error": "Invalid quiz ID provided for message link"}, status=400)

        ChatMessage.objects.create(
            session=session,
            message=message_content,
            is_user=is_user_message,
            quiz=quiz_instance # NEW: Assign quiz instance
        )
        return Response({"message": "Message saved"})

class CustomPagination(PageNumberPagination):
        page_size = 10
        page_size_query_param = 'page_size'
        max_page_size = 100

class SessionMemoryView(APIView):
    pagination_class = CustomPagination

    def get(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        # Get messages with quiz information using select_related for better performance
        messages = session.messages.select_related('quiz').order_by("created_at")
        
        # Build message list with quiz details
        message_list = []
        for message in messages:
            message_data = {
                "id": message.id,
                "message": message.message,
                "is_user": message.is_user,
                "created_at": message.created_at,
                "quiz": None
            }
            
            # Add quiz information if the message has an associated quiz
            if message.quiz:
                message_data["quiz"] = {
                    "id": message.quiz.id,
                    "title": message.quiz.title,
                    "description": message.quiz.description,
                    "num_questions": message.quiz.questions.count()
                }
            
            message_list.append(message_data)
        
        return Response({
            "messages": message_list,
            "pdf_uploaded": session.uploaded_pdf.name if session.uploaded_pdf else None
        })


class ListSessionsView(APIView):
    def get(self, request):
        sessions = ChatSession.objects.all().values("id", "created_at")
        return Response({"sessions": list(sessions)})
    
class CreateQuizView(APIView):
    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        title = request.data.get("title")
        description = request.data.get("description", "")

        if not title:
            return Response({"error": "Quiz title is required"}, status=400)

        quiz = Quiz.objects.create(session=session, title=title, description=description)
        return Response({"message": "Quiz created successfully", "quiz_id": quiz.id}, status=201)


class AddQuestionsView(APIView):
    def post(self, request, quiz_id):
        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Invalid quiz ID"}, status=404)

        questions_data = request.data.get("questions") 
        if not isinstance(questions_data, list) or not questions_data:
            return Response({"error": "List of questions is required"}, status=400)

        created_questions = []
        for q_data in questions_data:
            question_text = q_data.get("question_text")
            correct_answer = q_data.get("correct_answer", "")
            options = q_data.get("options", [])

            if not question_text:
               
                continue

            question = Question.objects.create(
                quiz=quiz,
                question_text=question_text,
                correct_answer=correct_answer,
                options=options
            )
            created_questions.append({
                "id": question.id, 
                "question_text": question.question_text,
                "options": question.options
            })

        return Response({"message": "Questions added successfully", "questions": created_questions}, status=201)


class GetQuizDetailsView(APIView):
    def get(self, request, quiz_id):
        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Invalid quiz ID"}, status=404)

        questions = quiz.questions.all().values("id", "question_text", "options")
        return Response({
            "id": quiz.id,
            "session_id": quiz.session.id if quiz.session else None,
            "title": quiz.title,
            "description": quiz.description,
            "created_at": quiz.created_at,
            "questions": list(questions)
        })

class SubmitQuizAnswersView(APIView):
    def post(self, request, quiz_id):

        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Invalid quiz ID"}, status=404)

        answers_data = request.data.get("answers") 
        if not isinstance(answers_data, list) or not answers_data:
            return Response({"error": "List of answers is required"}, status=400)

        submitted_answers = []
        for ans_data in answers_data:
            question_id = ans_data.get("question_id")
            user_answer_text = ans_data.get("user_answer", "")

            try:
                question = Question.objects.get(id=question_id, quiz=quiz)
            except Question.DoesNotExist:
                return Response({"error": f"Question {question_id} not found in this quiz"}, status=404)

            
            is_correct = None
            if question.correct_answer:
                is_correct = (user_answer_text.strip().lower() == question.correct_answer.strip().lower())

            attempt = UserQuizAttempt.objects.create(
                session=quiz.session,
                quiz=quiz,
                question=question,
                user_answer=user_answer_text,
                is_correct=is_correct
            )
            submitted_answers.append({
                "question_id": question.id,
                "question_text": question.question_text,
                "options": question.options,
                "user_answer": user_answer_text,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "attempt_id": attempt.id
            })


        return Response({"message": "Quiz answers submitted", "results": submitted_answers}, status=201)

class ListSessionQuizzesView(APIView):
    def get(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        quizzes = session.quizzes.all().values("id", "title", "description", "created_at")
        return Response({"quizzes": list(quizzes)})

class GetUserQuizAttemptsView(APIView):
    def get(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        quiz_id = request.query_params.get('quiz_id')

        attempts_query = session.quiz_attempts.all()
        if quiz_id:
            attempts_query = attempts_query.filter(quiz__id=quiz_id)

        attempts = attempts_query.order_by("attempted_at").values(
            "id",
            "quiz__id",
            "quiz__title",
            "question__id",
            "question__question_text",
            "user_answer",
            "is_correct",
            "attempted_at"
        )
        return Response({"attempts": list(attempts)})
    
class CreateGoalView(APIView):
    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        title = request.data.get("title")
        description = request.data.get("description", "")
        deadline_str = request.data.get("deadline")
        status = request.data.get("status", "pending") 

        if not title:
            return Response({"error": "Goal title is required"}, status=400)

        deadline = None
        if deadline_str:
            try:
                
                from datetime import datetime
                deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00')) 
            except ValueError:
                return Response({"error": "Invalid deadline format. Use ISO 8601 (e.g., 'YYYY-MM-DDTHH:MM:SSZ')"}, status=400)

        goal = Goal.objects.create(
            session=session,
            title=title,
            description=description,
            deadline=deadline,
            status=status
        )
        return Response({
            "message": "Goal created successfully",
            "goal_id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "deadline": goal.deadline,
            "status": goal.status,
            "created_at": goal.created_at
        }, status=201)


class ListGoalsView(APIView):
    def get(self, request):
        # return all goals
        goals = Goal.objects.all().order_by('deadline', 'created_at').values(
            "id", "title", "description", "deadline", "status", "created_at"
        )
        return Response({"goals": list(goals)})


class GoalDetailView(APIView):
    def get(self, request, goal_id):
        try:
            goal = Goal.objects.get(id=goal_id)
        except Goal.DoesNotExist:
            return Response({"error": "Goal not found"}, status=404)

        return Response({
            "id": goal.id,
            "session_id": goal.session.id if goal.session else None,
            "title": goal.title,
            "description": goal.description,
            "deadline": goal.deadline,
            "status": goal.status,
            "created_at": goal.created_at
        })

    def put(self, request, goal_id): 
        try:
            goal = Goal.objects.get(id=goal_id)
        except Goal.DoesNotExist:
            return Response({"error": "Goal not found"}, status=404)

        title = request.data.get("title", goal.title)
        description = request.data.get("description", goal.description)
        deadline_str = request.data.get("deadline", goal.deadline)
        status = request.data.get("status", goal.status)

        deadline = goal.deadline
        if deadline_str and deadline_str != goal.deadline: 
            try:
                from datetime import datetime
                
                if isinstance(deadline_str, str):
                    deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
                else: 
                    deadline = deadline_str
            except ValueError:
                return Response({"error": "Invalid deadline format. Use ISO 8601"}, status=400)


        goal.title = title
        goal.description = description
        goal.deadline = deadline
        goal.status = status
        goal.save()

        return Response({
            "message": "Goal updated successfully",
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "deadline": goal.deadline,
            "status": goal.status,
            "created_at": goal.created_at
        })

    def patch(self, request, goal_id): 
        try:
            goal = Goal.objects.get(id=goal_id)
        except Goal.DoesNotExist:
            return Response({"error": "Goal not found"}, status=404)

        for key, value in request.data.items():
            if key == "deadline":
                if value:
                    try:
                        from datetime import datetime
                        setattr(goal, key, datetime.fromisoformat(value.replace('Z', '+00:00')))
                    except ValueError:
                        return Response({"error": "Invalid deadline format. Use ISO 8601"}, status=400)
                else: #
                    setattr(goal, key, None)
            else:
                setattr(goal, key, value)
        goal.save()

        return Response({
            "message": "Goal updated successfully",
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "deadline": goal.deadline,
            "status": goal.status,
            "created_at": goal.created_at
        })

    def delete(self, request, goal_id):
        try:
            goal = Goal.objects.get(id=goal_id)
        except Goal.DoesNotExist:
            return Response({"error": "Goal not found"}, status=404)

        goal.delete()
        return Response({"message": "Goal deleted successfully"}, status=204)

class StreamingRagAnswerView(APIView):
    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Invalid session ID"}, status=404)

        query = request.data.get("query") 
        if not query:
            return Response({"error": "Query is required"}, status=400)

        # Initialize Groq client
        try:
            groq_client = Groq(api_key=getattr(settings, 'GROQ_API_KEY', ''))
            
            def generate_response():
                """Generator function for streaming response"""
                try:
                    for chunk_data in generate_streaming_assistant_response(
                        query=query,
                        session_id=session_id,
                        groq_client=groq_client
                    ):
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        print(chunk_data)
                        if chunk_data.get("done", False):
                            break
                except Exception as e:
                    error_chunk = {"chunk": "", "done": True, "error": str(e)}
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                    print(f"Streaming error: {str(e)}")

            response = StreamingHttpResponse(
                generate_response(),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['Connection'] = 'keep-alive'
            response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
            
            return response
                
        except Exception as e:
            return Response({"error": f"Streaming error: {str(e)}"}, status=500)

class GenerateQuizFromMessageView(APIView):
    def post(self, request, message_id):
        """
        Generate a quiz from a specific message using Groq
        """
        try:
            # Get the message
            message = ChatMessage.objects.get(id=message_id)
        except ChatMessage.DoesNotExist:
            return Response({"error": "Message not found"}, status=404)
        
        # Check if a quiz already exists for this message
        existing_quiz = Quiz.objects.filter(chat_messages=message).first()
        if existing_quiz:
            return Response({
                "error": "Quiz already exists for this message",
                "quiz_id": existing_quiz.id
            }, status=400)
        
        try:
            # Initialize Groq client
            groq_client = Groq(api_key=settings.GROQ_API_KEY)
            
            # Create quiz generation prompt
            quiz_prompt = f"""### Role
You're a Quiz Generation Assistant. Create a comprehensive quiz based on the given message content.

### Task
Generate a quiz with 5 multiple choice questions based on the message content. Focus on key concepts, important details, and practical applications.

### Output Format
Return a JSON object with this structure:
{{
  "title": "Quiz title based on the message content",
  "description": "Brief description of what this quiz covers",
  "questions": [
    {{
      "question_text": "Question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Correct option text (must match one of the options exactly)"
    }}
  ]
}}

### Message Content
{message.message}

### Instructions
- Create questions that test understanding of the main concepts
- Make sure all options are plausible but only one is correct
- Keep questions clear and concise
- Ensure the correct_answer exactly matches one of the options#

# Rules:
# Output only a VALID JSON object with the structure specified above.
# Do not include any other text or comments."""

            # Generate quiz using Groq
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a quiz generation assistant. Always return valid JSON."},
                    {"role": "user", "content": quiz_prompt}
                ],
                model=settings.MODEL,
                temperature=0.7,
                max_tokens=3000
            )
            
            quiz_data_text = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            # quiz_data_text = quiz_data_text.replace("```json", "").replace("```", "")
            # print(quiz_data_text, file=open("quiz_data_text.json", "w"))
            try:
                quiz_data = json.loads(quiz_data_text)
            except json.JSONDecodeError:
                return Response({"error": "Failed to generate valid quiz data"}, status=500)
            
            # Create the quiz
            quiz = Quiz.objects.create(
                session=message.session,
                title=quiz_data.get("title", f"Quiz for Message {message_id}"),
                description=quiz_data.get("description", "")
            )
            
            # Link the quiz to the message
            message.quiz = quiz
            message.save()
            
            # Create questions
            created_questions = []
            for q_data in quiz_data.get("questions", []):
                question = Question.objects.create(
                    quiz=quiz,
                    question_text=q_data.get("question_text", ""),
                    correct_answer=q_data.get("correct_answer", ""),
                    options=q_data.get("options", [])
                )
                created_questions.append({
                    "id": question.id,
                    "question_text": question.question_text,
                    "options": question.options,
                    "correct_answer": question.correct_answer
                })
            
            return Response({
                "message": "Quiz generated successfully",
                "quiz_id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "questions": created_questions
            }, status=201)
            
        except Exception as e:
            traceback.print_exc()
            return Response({
                "error": f"Failed to generate quiz: {str(e)}"
            }, status=500)


class ListAllQuizzesView(APIView):
    def get(self, request):
        """
        List all quizzes across all sessions with pagination
        """
        try:
            # Get all quizzes with related data
            quizzes = Quiz.objects.select_related('session').prefetch_related('questions').all()
            
            # Apply pagination
            paginator = CustomPagination()
            paginated_quizzes = paginator.paginate_queryset(quizzes, request)
            
            quiz_list = []
            for quiz in paginated_quizzes:
                quiz_data = {
                    "id": quiz.id,
                    "title": quiz.title,
                    "description": quiz.description,
                    "session_id": quiz.session.id if quiz.session else None,
                    "created_at": quiz.created_at,
                    "question_count": quiz.questions.count(),
                    "linked_message_id": None
                }
                
                # Find the linked message
                linked_message = quiz.chat_messages.first()
                if linked_message:
                    quiz_data["linked_message_id"] = linked_message.id
                
                quiz_list.append(quiz_data)
            
            return paginator.get_paginated_response(quiz_list)
            
        except Exception as e:
            traceback.print_exc()
            return Response({
                "error": f"Failed to retrieve quizzes: {str(e)}"
            }, status=500)

