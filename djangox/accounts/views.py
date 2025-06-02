from django.shortcuts import render

def movie_detail(request, movie_id):
    return render(request, 'app/movie_detail.html', {'movie_id': movie_id})