from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']  # 允许用户填写评分和评论
        widgets = {
            'rating': forms.Select(choices=[(i, i) for i in range(1, 6)]),  # 显示1到5的评分选项
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter your review here...'})
        }



