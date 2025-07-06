from django.contrib import admin
from .models import GlobalMemory, ChatSession, ChatMessage, Quiz, Question, UserQuizAttempt, Goal

admin.site.register(GlobalMemory)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(UserQuizAttempt)
admin.site.register(Goal)
# Register your models here.
