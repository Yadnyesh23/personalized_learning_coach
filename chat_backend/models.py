from django.db import models

class GlobalMemory(models.Model):
    preferences = models.TextField() 

    def __str__(self):
        return "Global Preferences"

class ChatSession(models.Model):
    uploaded_pdf = models.FileField(upload_to='pdfs/', null=True, blank=True) # PDF upload is per-session
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat Session {self.id}"

class Quiz(models.Model):
    title = models.CharField(max_length=255)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='quizzes')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz {self.id}: {self.title} (Session: {self.session_id if self.session else 'N/A'})"

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    is_user = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.SET_NULL, related_name='chat_messages', null=True, blank=True)


    def __str__(self):
        return f"Session {self.session.id} - {'User' if self.is_user else 'Bot'}: {self.message[:50]}..."

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    correct_answer = models.TextField(blank=True)
    options = models.JSONField(default=list, blank=True)  # Store multiple choice options as JSON array
 
    def __str__(self):
        return f"Q {self.id} for Quiz {self.quiz.id}: {self.question_text[:50]}..."

class UserQuizAttempt(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers', null=True, blank=True)
    user_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True) # Null for ungraded, True/False after checking
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attempt {self.id} for Quiz {self.quiz.id} by Session {self.session.id}"

class Goal(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='goals', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending') # e.g., 'pending', 'in progress', 'completed', 'failed'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Goal {self.id}: {self.title} (Status: {self.status})"