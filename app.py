import os
import requests
import random
from flask import Flask, render_template, request, redirect, url_for, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-ddd-os')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ddd_os.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── MODELS ─────────────────────────────────────────────────────────────────

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    task_type = db.Column(db.String(50), nullable=False, default='task')
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    related_book_id = db.Column(db.Integer, nullable=True)
    goal = db.Column(db.String(100), nullable=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    category = db.Column(db.String(50), default='general')
    total_pages = db.Column(db.Integer, default=1)
    pages_read = db.Column(db.Integer, default=0)
    cover_url = db.Column(db.String(500))
    is_reading = db.Column(db.Boolean, default=False)

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    total_episodes = db.Column(db.Integer, default=12)
    episodes_watched = db.Column(db.Integer, default=0)
    cover_url = db.Column(db.String(500))
    is_watching = db.Column(db.Boolean, default=False)

class Manga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    total_chapters = db.Column(db.Integer, default=0)
    chapters_read = db.Column(db.Integer, default=0)
    cover_url = db.Column(db.String(500))
    is_reading = db.Column(db.Boolean, default=False)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    total_minutes = db.Column(db.Integer, default=0)
    last_practiced = db.Column(db.Date, nullable=True)

class SkillLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    notes = db.Column(db.String(300))
    skill = db.relationship('Skill', backref='logs')

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='🔔')
    notes = db.Column(db.Text)
    last_done = db.Column(db.Date, nullable=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='📁')
    color = db.Column(db.String(20), default='#0984e3')
    description = db.Column(db.Text)
    tasks = db.relationship('ProjectTask', backref='project', cascade='all, delete-orphan')

class ProjectTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    calendar_date = db.Column(db.Date, nullable=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='✅')
    logs = db.relationship('HabitLog', backref='habit', cascade='all, delete-orphan')

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)


# ── XP / LEVEL SYSTEM ──────────────────────────────────────────────────────

LEVEL_THRESHOLDS = [
    (0,     'Novice',       '#b2bec3'),
    (60,    'Beginner',     '#74b9ff'),
    (180,   'Apprentice',   '#55efc4'),
    (360,   'Developing',   '#fdcb6e'),
    (720,   'Intermediate', '#e17055'),
    (1500,  'Practiced',    '#a29bfe'),
    (3000,  'Skilled',      '#fd79a8'),
    (6000,  'Advanced',     '#00b894'),
    (12000, 'Expert',       '#0984e3'),
    (24000, 'Master',       '#6c5ce7'),
]

def get_skill_level(xp):
    level_idx = 0
    for i, (threshold, _, _) in enumerate(LEVEL_THRESHOLDS):
        if xp >= threshold:
            level_idx = i
    current = LEVEL_THRESHOLDS[level_idx]
    is_max = level_idx == len(LEVEL_THRESHOLDS) - 1
    next_lvl = LEVEL_THRESHOLDS[level_idx + 1] if not is_max else None
    xp_in_level = xp - current[0]
    xp_to_next = (next_lvl[0] - current[0]) if next_lvl else 1
    pct = min(100, round(xp_in_level / xp_to_next * 100, 1)) if xp_to_next else 100
    return {
        'level': level_idx + 1,
        'name': current[1],
        'color': current[2],
        'xp': xp,
        'xp_in_level': xp_in_level,
        'xp_to_next': xp_to_next,
        'pct': pct,
        'is_max': is_max,
    }


# ── SEEDS ──────────────────────────────────────────────────────────────────

SKILLS_SEED = [
    ('Drawing Architecture', 'Drawing'),
    ('Drawing People', 'Drawing'),
    ('Drawing Manga', 'Drawing'),
    ('Photoshop', 'Design Software'),
    ('Illustrator', 'Design Software'),
    ('InDesign', 'Design Software'),
    ('Rhino 8', 'Design Software'),
    ('Grasshopper', 'Design Software'),
    ('Revit', 'Design Software'),
    ('D5 Render', 'Design Software'),
    ('Twinmotion', 'Design Software'),
    ('Product Design', 'Design'),
    ('Building Presentation', 'Design'),
    ('Digital Design', 'Design'),
    ('Writing', 'Creative'),
    ('Coding Web Pages', 'Creative'),
    ('Coding Tools', 'Creative'),
    ('Violin', 'Physical'),
    ('Workout', 'Physical'),
]

REMINDERS_SEED = [
    ('Post on Instagram', '📸'),
    ('Update LinkedIn', '💼'),
    ('Work on Portfolio Website', '🌐'),
    ('Work on DDD OS', '🛠️'),
]

PROJECTS_SEED = [
    ('Make Personalised Calendar Tool', '🛠️', '#0984e3', [
        'Design database schema',
        'Build Flask backend',
        'Add media tracking pages',
        'Add skills tracker',
        'Polish UI and deploy',
    ]),
    ('DDD Website', '🌐', '#6c5ce7', [
        'Update portfolio with new projects',
        'Improve AI tools section',
        'Add project case studies',
        'Improve mobile layout',
    ]),
    ('IOP2', '🏛️', '#00b894', [
        'Research site and context',
        'Develop initial concept',
        'Create design drawings',
        'Build physical model',
        'Prepare final presentation',
    ]),
]

HABITS_SEED = [
    ('Morning workout', '💪'),
    ('Read 20 pages', '📖'),
    ('Practice violin', '🎻'),
    ('No social media before noon', '📵'),
]


with app.app_context():
    db.create_all()
    for sql in [
        "ALTER TABLE book ADD COLUMN category VARCHAR(50) DEFAULT 'general'",
    ]:
        try:
            db.session.execute(db.text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()

    if Skill.query.count() == 0:
        for name, cat in SKILLS_SEED:
            db.session.add(Skill(name=name, category=cat))
        db.session.commit()

    if Reminder.query.count() == 0:
        for title, icon in REMINDERS_SEED:
            db.session.add(Reminder(title=title, icon=icon))
        db.session.commit()

    if Project.query.count() == 0:
        for name, icon, color, tasks in PROJECTS_SEED:
            p = Project(name=name, icon=icon, color=color)
            db.session.add(p)
            db.session.flush()
            for t in tasks:
                db.session.add(ProjectTask(project_id=p.id, title=t))
        db.session.commit()

    if Habit.query.count() == 0:
        for name, icon in HABITS_SEED:
            db.session.add(Habit(name=name, icon=icon))
        db.session.commit()


# ── CALENDAR ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    date_str = request.args.get('date')
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    start_of_week = target_date - timedelta(days=target_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    tasks = Task.query.filter(
        Task.date >= start_of_week, Task.date <= week_dates[-1]
    ).order_by(Task.is_completed, Task.time).all()
    books = {b.id: b for b in Book.query.all()}
    prev_week = (start_of_week - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (start_of_week + timedelta(days=7)).strftime('%Y-%m-%d')
    return render_template('calendar.html', tasks=tasks, week_dates=week_dates,
                           prev_week=prev_week, next_week=next_week,
                           current_week=date.today().strftime('%Y-%m-%d'),
                           books=books, today=date.today(), active='calendar')

@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        book_id = request.form.get('related_book_id')
        new_task = Task(
            title=request.form['title'],
            task_type=request.form['task_type'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            time=request.form['time'],
            related_book_id=int(book_id) if book_id else None,
            goal=request.form.get('goal'),
        )
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('index'))
    active_books = Book.query.filter_by(is_reading=True).all()
    return render_template('task_form.html', task=None, active_books=active_books)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        task.title = request.form['title']
        task.task_type = request.form['task_type']
        task.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        task.time = request.form['time']
        book_id = request.form.get('related_book_id')
        task.related_book_id = int(book_id) if book_id else None
        task.goal = request.form.get('goal')
        db.session.commit()
        return redirect(url_for('index'))
    active_books = Book.query.filter_by(is_reading=True).all()
    return render_template('task_form.html', task=task, active_books=active_books)

@app.route('/delete/<int:id>')
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/toggle/<int:id>')
def toggle_task(id):
    task = Task.query.get_or_404(id)
    task.is_completed = not task.is_completed
    db.session.commit()
    return redirect(request.referrer or url_for('index'))


# ── BOOKS ──────────────────────────────────────────────────────────────────

@app.route('/media/books')
def books_page():
    category = request.args.get('category', 'all')
    current_book = Book.query.filter_by(is_reading=True).first()
    q = Book.query.filter_by(is_reading=False)
    if category != 'all':
        q = q.filter_by(category=category)
    return render_template('books.html', current_book=current_book, books=q.all(),
                           category=category, active='books')

@app.route('/add_book', methods=['POST'])
def add_book():
    query = request.form.get('search_query')
    category = request.form.get('category', 'general')
    resp = requests.get("https://www.googleapis.com/books/v1/volumes",
                        params={"q": query, "maxResults": 5})
    books_data = []
    if resp.status_code == 200 and 'items' in resp.json():
        for item in resp.json()['items']:
            v = item.get('volumeInfo', {})
            books_data.append({
                'title': v.get('title', 'Unknown Title'),
                'author': v.get('authors', ['Unknown'])[0] if 'authors' in v else 'Unknown',
                'page_count': v.get('pageCount', 300),
                'thumbnail': v.get('imageLinks', {}).get('thumbnail', ''),
                'category': category,
            })
    return render_template('select_book.html', books=books_data, category=category)

@app.route('/confirm_book', methods=['POST'])
def confirm_book():
    db.session.add(Book(
        title=request.form['title'],
        author=request.form['author'],
        total_pages=int(request.form['page_count']),
        cover_url=request.form['thumbnail'],
        category=request.form.get('category', 'general'),
        is_reading=Book.query.count() == 0,
    ))
    db.session.commit()
    return redirect(url_for('books_page'))

@app.route('/update_progress/<int:id>', methods=['POST'])
def update_progress(id):
    book = Book.query.get_or_404(id)
    book.pages_read = min(int(request.form.get('pages_read', 0)), book.total_pages)
    if book.pages_read >= book.total_pages:
        book.is_reading = False
    db.session.commit()
    return redirect(url_for('books_page'))

@app.route('/set_reading/<int:id>')
def set_reading(id):
    Book.query.filter_by(is_reading=True).update({'is_reading': False})
    Book.query.get_or_404(id).is_reading = True
    db.session.commit()
    return redirect(url_for('books_page'))

@app.route('/delete_book/<int:id>')
def delete_book(id):
    db.session.delete(Book.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('books_page'))


# ── ANIME ──────────────────────────────────────────────────────────────────

@app.route('/media/anime')
def anime_page():
    return render_template('anime.html',
                           current_anime=Anime.query.filter_by(is_watching=True).first(),
                           animes=Anime.query.filter_by(is_watching=False).all(),
                           active='anime')

@app.route('/add_anime', methods=['POST'])
def add_anime():
    resp = requests.get("https://api.jikan.moe/v4/anime",
                        params={"q": request.form.get('search_query'), "limit": 5})
    anime_data = []
    if resp.status_code == 200:
        for item in resp.json().get('data', []):
            anime_data.append({
                'title': item.get('title_english') or item.get('title', 'Unknown'),
                'total_episodes': item.get('episodes') or 12,
                'thumbnail': item.get('images', {}).get('jpg', {}).get('image_url', ''),
            })
    return render_template('select_anime.html', animes=anime_data)

@app.route('/confirm_anime', methods=['POST'])
def confirm_anime():
    db.session.add(Anime(
        title=request.form['title'],
        total_episodes=int(request.form['total_episodes']),
        cover_url=request.form['thumbnail'],
        is_watching=Anime.query.count() == 0,
    ))
    db.session.commit()
    return redirect(url_for('anime_page'))

@app.route('/update_anime_progress/<int:id>', methods=['POST'])
def update_anime_progress(id):
    anime = Anime.query.get_or_404(id)
    anime.episodes_watched = min(int(request.form.get('episodes_watched', 0)), anime.total_episodes)
    if anime.episodes_watched >= anime.total_episodes:
        anime.is_watching = False
    db.session.commit()
    return redirect(url_for('anime_page'))

@app.route('/set_watching_anime/<int:id>')
def set_watching_anime(id):
    Anime.query.filter_by(is_watching=True).update({'is_watching': False})
    Anime.query.get_or_404(id).is_watching = True
    db.session.commit()
    return redirect(url_for('anime_page'))

@app.route('/delete_anime/<int:id>')
def delete_anime(id):
    db.session.delete(Anime.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('anime_page'))


# ── MANGA ──────────────────────────────────────────────────────────────────

@app.route('/media/manga')
def manga_page():
    return render_template('manga.html',
                           current_manga=Manga.query.filter_by(is_reading=True).first(),
                           mangas=Manga.query.filter_by(is_reading=False).all(),
                           active='manga')

@app.route('/add_manga', methods=['POST'])
def add_manga():
    resp = requests.get("https://api.jikan.moe/v4/manga",
                        params={"q": request.form.get('search_query'), "limit": 5})
    manga_data = []
    if resp.status_code == 200:
        for item in resp.json().get('data', []):
            manga_data.append({
                'title': item.get('title_english') or item.get('title', 'Unknown'),
                'total_chapters': item.get('chapters') or 0,
                'thumbnail': item.get('images', {}).get('jpg', {}).get('image_url', ''),
            })
    return render_template('select_manga.html', mangas=manga_data)

@app.route('/confirm_manga', methods=['POST'])
def confirm_manga():
    db.session.add(Manga(
        title=request.form['title'],
        total_chapters=int(request.form['total_chapters']),
        cover_url=request.form['thumbnail'],
        is_reading=Manga.query.count() == 0,
    ))
    db.session.commit()
    return redirect(url_for('manga_page'))

@app.route('/update_manga_progress/<int:id>', methods=['POST'])
def update_manga_progress(id):
    manga = Manga.query.get_or_404(id)
    manga.chapters_read = int(request.form.get('chapters_read', 0))
    if manga.total_chapters > 0 and manga.chapters_read >= manga.total_chapters:
        manga.is_reading = False
    db.session.commit()
    return redirect(url_for('manga_page'))

@app.route('/set_reading_manga/<int:id>')
def set_reading_manga(id):
    Manga.query.filter_by(is_reading=True).update({'is_reading': False})
    Manga.query.get_or_404(id).is_reading = True
    db.session.commit()
    return redirect(url_for('manga_page'))

@app.route('/delete_manga/<int:id>')
def delete_manga(id):
    db.session.delete(Manga.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('manga_page'))


# ── SKILLS ─────────────────────────────────────────────────────────────────

@app.route('/skills')
def skills_page():
    skills = Skill.query.order_by(Skill.category, Skill.name).all()
    categories = {}
    for skill in skills:
        categories.setdefault(skill.category, []).append(skill)
    skill_levels = {s.id: get_skill_level(s.total_minutes) for s in skills}
    return render_template('skills.html', categories=categories, today=date.today(),
                           active='skills', skill_levels=skill_levels)

@app.route('/skills/log/<int:id>', methods=['POST'])
def log_skill(id):
    skill = Skill.query.get_or_404(id)
    duration = int(request.form.get('duration', 30))
    skill.total_minutes += duration
    skill.last_practiced = date.today()
    db.session.add(SkillLog(
        skill_id=id, date=date.today(),
        duration_minutes=duration, notes=request.form.get('notes', ''),
    ))
    db.session.commit()
    return redirect(url_for('skills_page'))


# ── PRESENTATION ───────────────────────────────────────────────────────────

@app.route('/presentation')
def presentation_page():
    project_data = []
    for p in Project.query.all():
        tasks = p.tasks
        done = sum(1 for t in tasks if t.is_completed)
        project_data.append({'project': p, 'tasks': tasks, 'total': len(tasks), 'done': done})
    return render_template('presentation.html',
                           reminders=Reminder.query.all(),
                           project_data=project_data,
                           today=date.today(), active='presentation')

@app.route('/reminder/done/<int:id>')
def reminder_done(id):
    Reminder.query.get_or_404(id).last_done = date.today()
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/reminder/add', methods=['POST'])
def add_reminder():
    db.session.add(Reminder(
        title=request.form['title'],
        icon=request.form.get('icon', '🔔'),
        notes=request.form.get('notes', ''),
    ))
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/reminder/delete/<int:id>')
def delete_reminder(id):
    db.session.delete(Reminder.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/project/add', methods=['POST'])
def add_project():
    p = Project(
        name=request.form['name'],
        icon=request.form.get('icon', '📁'),
        color=request.form.get('color', '#0984e3'),
        description=request.form.get('description', ''),
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/project/delete/<int:id>')
def delete_project(id):
    db.session.delete(Project.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/project/<int:pid>/task/add', methods=['POST'])
def add_project_task(pid):
    Project.query.get_or_404(pid)
    title = request.form.get('title', '').strip()
    cal_date_str = request.form.get('calendar_date', '')
    cal_date = datetime.strptime(cal_date_str, '%Y-%m-%d').date() if cal_date_str else None
    db.session.add(ProjectTask(project_id=pid, title=title, calendar_date=cal_date))
    if cal_date:
        db.session.add(Task(title=title, task_type='task', date=cal_date))
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/project/task/toggle/<int:id>')
def toggle_project_task(id):
    pt = ProjectTask.query.get_or_404(id)
    pt.is_completed = not pt.is_completed
    db.session.commit()
    return redirect(url_for('presentation_page'))

@app.route('/project/task/delete/<int:id>')
def delete_project_task(id):
    db.session.delete(ProjectTask.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('presentation_page'))


# ── HABITS ─────────────────────────────────────────────────────────────────

@app.route('/habits')
def habits_page():
    today = date.today()
    habit_data = []
    for h in Habit.query.all():
        log_dates = {log.date for log in h.logs}
        done_today = today in log_dates
        streak, check = 0, today
        while check in log_dates:
            streak += 1
            check -= timedelta(days=1)
        habit_data.append({'habit': h, 'done_today': done_today, 'streak': streak})
    return render_template('habits.html', habit_data=habit_data, today=today, active='habits')

@app.route('/habits/log/<int:id>')
def log_habit(id):
    today = date.today()
    if not HabitLog.query.filter_by(habit_id=id, date=today).first():
        db.session.add(HabitLog(habit_id=id, date=today))
        db.session.commit()
    return redirect(url_for('habits_page'))

@app.route('/habits/unlog/<int:id>')
def unlog_habit(id):
    log = HabitLog.query.filter_by(habit_id=id, date=date.today()).first()
    if log:
        db.session.delete(log)
        db.session.commit()
    return redirect(url_for('habits_page'))

@app.route('/habits/add', methods=['POST'])
def add_habit():
    db.session.add(Habit(name=request.form['name'], icon=request.form.get('icon', '✅')))
    db.session.commit()
    return redirect(url_for('habits_page'))

@app.route('/habits/delete/<int:id>')
def delete_habit(id):
    db.session.delete(Habit.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('habits_page'))


# ── SPIN ───────────────────────────────────────────────────────────────────

@app.route('/spin')
def spin_page():
    today = date.today()
    skills = Skill.query.all()
    unpracticed = [s for s in skills if s.last_practiced != today]
    suggested_skill = random.choice(unpracticed) if unpracticed else (random.choice(skills) if skills else None)
    suggestions = []
    books_bl = Book.query.filter_by(is_reading=False).all()
    anime_bl = Anime.query.filter_by(is_watching=False).all()
    manga_bl = Manga.query.filter_by(is_reading=False).all()
    if books_bl:
        suggestions.append({'icon': '📚', 'title': random.choice(books_bl).title, 'type': 'Book'})
    if anime_bl:
        suggestions.append({'icon': '🎬', 'title': random.choice(anime_bl).title, 'type': 'Anime'})
    if manga_bl:
        suggestions.append({'icon': '📖', 'title': random.choice(manga_bl).title, 'type': 'Manga'})
    return render_template('spin.html', suggested_skill=suggested_skill,
                           suggestions=suggestions, active='spin')


# ── STATS ──────────────────────────────────────────────────────────────────

@app.route('/stats')
def stats_page():
    today = date.today()
    thirty_ago = today - timedelta(days=29)
    skills = Skill.query.all()

    category_hours = {}
    for s in skills:
        category_hours[s.category] = category_hours.get(s.category, 0) + s.total_minutes
    category_hours = {k: round(v / 60, 1) for k, v in
                      sorted(category_hours.items(), key=lambda x: -x[1])}

    top_skill = max(skills, key=lambda s: s.total_minutes) if skills else None
    total_skill_hours = sum(s.total_minutes for s in skills) // 60

    activity_map = {}
    for log in SkillLog.query.filter(SkillLog.date >= thirty_ago).all():
        k = log.date.isoformat()
        activity_map[k] = activity_map.get(k, 0) + log.duration_minutes

    heatmap = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        mins = activity_map.get(d.isoformat(), 0)
        intensity = 0 if mins == 0 else 1 if mins < 30 else 2 if mins < 60 else 3 if mins < 120 else 4
        heatmap.append({'date': d, 'mins': mins, 'intensity': intensity})

    habit_streaks = []
    for h in Habit.query.all():
        log_dates = {log.date for log in h.logs}
        streak, check = 0, today
        while check in log_dates:
            streak += 1
            check -= timedelta(days=1)
        habit_streaks.append({'name': h.name, 'icon': h.icon, 'streak': streak})
    habit_streaks.sort(key=lambda x: -x['streak'])

    return render_template('stats.html',
                           books_total=Book.query.count(),
                           anime_total=Anime.query.count(),
                           manga_total=Manga.query.count(),
                           category_hours=category_hours,
                           top_skill=top_skill,
                           total_skill_hours=total_skill_hours,
                           heatmap=heatmap,
                           habit_streaks=habit_streaks,
                           active='stats')


@app.route('/sw.js')
def service_worker():
    resp = make_response(send_from_directory('static', 'sw.js'))
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Content-Type'] = 'application/javascript'
    return resp


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true')
