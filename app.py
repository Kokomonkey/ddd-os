import os
import uuid
import requests
import random
from flask import Flask, render_template, request, redirect, url_for, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-ddd-os')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ddd_os.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'diary_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    # Bookcase grouping
    series = db.Column(db.String(120), default='')          # e.g. "Discworld"
    subseries = db.Column(db.String(120), default='')       # e.g. "City Watch"
    series_order = db.Column(db.Integer, default=0)         # reading order within series
    publisher = db.Column(db.String(120), default='')       # e.g. "Corgi"
    year = db.Column(db.Integer, nullable=True)
    isbn = db.Column(db.String(20), default='')

    @property
    def is_finished(self):
        return self.total_pages > 0 and self.pages_read >= self.total_pages

    @property
    def progress_pct(self):
        if not self.total_pages:
            return 0
        return min(100, int(round(self.pages_read / self.total_pages * 100)))

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

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer, nullable=True)
    runtime = db.Column(db.Integer, default=120)  # minutes
    cover_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='watchlist')  # watchlist / watched
    rating = db.Column(db.Integer, nullable=True)  # 1-5
    watched_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)

class Series(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    total_episodes = db.Column(db.Integer, default=10)
    episodes_watched = db.Column(db.Integer, default=0)
    total_seasons = db.Column(db.Integer, default=1)
    cover_url = db.Column(db.String(500))
    is_watching = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Integer, nullable=True)

class Boardgame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    min_players = db.Column(db.Integer, default=2)
    max_players = db.Column(db.Integer, default=4)
    avg_playtime = db.Column(db.Integer, default=60)  # minutes
    cover_url = db.Column(db.String(500))
    times_played = db.Column(db.Integer, default=0)
    last_played = db.Column(db.Date, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    is_in_collection = db.Column(db.Boolean, default=True)

class DailyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    free_time_minutes = db.Column(db.Integer, default=180)
    mode = db.Column(db.String(30), default='balanced')  # locked / reward / fun / balanced
    notes = db.Column(db.Text)
    suggested_task_ids = db.Column(db.String(500), default='')  # comma-separated ProjectTask ids

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    energy = db.Column(db.Integer, nullable=True)   # 1-5
    mood = db.Column(db.Integer, nullable=True)     # 1-5
    win = db.Column(db.String(300))                 # "today's win"
    notes = db.Column(db.Text)

class RewardLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    reward_description = db.Column(db.String(300))
    earned = db.Column(db.Boolean, default=False)

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
    color = db.Column(db.String(20), default='#d4a373')
    description = db.Column(db.Text)
    # New priority/progress fields
    priority = db.Column(db.String(20), default='want')  # must / have / want / fun
    effort = db.Column(db.String(5), default='M')        # S / M / L / XL
    percent_complete = db.Column(db.Integer, default=0)  # 0-100
    deadline = db.Column(db.Date, nullable=True)
    tags = db.Column(db.String(300), default='')        # comma-separated
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Date, default=date.today)
    tasks = db.relationship('ProjectTask', backref='project', cascade='all, delete-orphan')

    @property
    def almost_done(self):
        return self.percent_complete >= 75 and self.percent_complete < 100

    @property
    def is_fun(self):
        return self.priority == 'fun'

    @property
    def computed_percent(self):
        """If there are tasks, derive from tasks; else use manual percent_complete."""
        if self.tasks:
            done = sum(1 for t in self.tasks if t.is_completed)
            return int(round(done / len(self.tasks) * 100))
        return self.percent_complete or 0

class ProjectTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    calendar_date = db.Column(db.Date, nullable=True)
    effort_minutes = db.Column(db.Integer, default=30)  # estimated time
    completed_at = db.Column(db.Date, nullable=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='✅')
    logs = db.relationship('HabitLog', backref='habit', cascade='all, delete-orphan')

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)

class DiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    felt_pressure = db.Column(db.Integer, nullable=True)
    workload = db.Column(db.Integer, nullable=True)
    direction_clarity = db.Column(db.Integer, nullable=True)
    design_vision = db.Column(db.Integer, nullable=True)
    design_satisfaction = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

class DiaryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    method = db.Column(db.String(200), nullable=True)
    intent = db.Column(db.Text, nullable=True)
    insight = db.Column(db.Text, nullable=True)


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
    ('Make Personalised Calendar Tool', '🛠️', '#d4a373', 'have', 'L', [
        'Design database schema',
        'Build Flask backend',
        'Add media tracking pages',
        'Add skills tracker',
        'Polish UI and deploy',
    ]),
    ('DDD Website', '🌐', '#9c6644', 'must', 'L', [
        'Update portfolio with new projects',
        'Improve AI tools section',
        'Add project case studies',
        'Improve mobile layout',
    ]),
    ('IOP2', '🏛️', '#7f5539', 'must', 'XL', [
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

# ── DISCWORLD SEED ─────────────────────────────────────────────────────────
# 41 main Discworld novels by Terry Pratchett.
# ISBNs are the UK Corgi/Transworld paperback editions where available
# (Eric was originally Gollancz, The Last Hero is Gollancz illustrated).
# Cover URLs use Open Library's by-ISBN service (no API key required).
# Format: (order, title, year, pages, isbn, subseries)
DISCWORLD_SEED = [
    (1,  'The Colour of Magic',                  1983, 285, '0552124753', 'Rincewind'),
    (2,  'The Light Fantastic',                  1986, 285, '0552124745', 'Rincewind'),
    (3,  'Equal Rites',                          1987, 287, '0552131059', 'Witches'),
    (4,  'Mort',                                 1987, 272, '0552131067', 'Death'),
    (5,  'Sourcery',                             1988, 272, '0552131075', 'Rincewind'),
    (6,  'Wyrd Sisters',                         1988, 285, '0552134600', 'Witches'),
    (7,  'Pyramids',                             1989, 382, '0552134619', 'Standalone'),
    (8,  'Guards! Guards!',                      1989, 382, '0552134627', 'City Watch'),
    (9,  'Eric',                                 1990, 155, '0575600003', 'Rincewind'),
    (10, 'Moving Pictures',                      1990, 382, '0552134635', 'Industrial Revolution'),
    (11, 'Reaper Man',                           1991, 287, '0552134643', 'Death'),
    (12, 'Witches Abroad',                       1991, 286, '0552134651', 'Witches'),
    (13, 'Small Gods',                           1992, 382, '055213890X', 'Standalone'),
    (14, 'Lords and Ladies',                     1992, 382, '0552138916', 'Witches'),
    (15, 'Men at Arms',                          1993, 382, '0552140287', 'City Watch'),
    (16, 'Soul Music',                           1994, 382, '0552140295', 'Death'),
    (17, 'Interesting Times',                    1994, 352, '0552142352', 'Rincewind'),
    (18, 'Maskerade',                            1995, 382, '0552142360', 'Witches'),
    (19, 'Feet of Clay',                         1996, 415, '0552142379', 'City Watch'),
    (20, 'Hogfather',                            1996, 445, '0552145424', 'Death'),
    (21, 'Jingo',                                1997, 448, '0552145432', 'City Watch'),
    (22, 'The Last Continent',                   1998, 410, '0552146145', 'Rincewind'),
    (23, 'Carpe Jugulum',                        1998, 424, '0552146153', 'Witches'),
    (24, 'The Fifth Elephant',                   1999, 423, '0552146161', 'City Watch'),
    (25, 'The Truth',                            2000, 444, '055214768X', 'Industrial Revolution'),
    (26, 'Thief of Time',                        2001, 432, '0552148407', 'Death'),
    (27, 'The Last Hero',                        2001, 160, '057507978X', 'Rincewind'),
    (28, 'The Amazing Maurice and his Educated Rodents', 2001, 272, '0552546933', 'Young Adult'),
    (29, 'Night Watch',                          2002, 474, '0552148997', 'City Watch'),
    (30, 'The Wee Free Men',                     2003, 317, '0552549053', 'Tiffany Aching'),
    (31, 'Monstrous Regiment',                   2003, 493, '0552149411', 'Standalone'),
    (32, 'A Hat Full of Sky',                    2004, 324, '0552551449', 'Tiffany Aching'),
    (33, 'Going Postal',                         2004, 474, '055214943X', 'Moist von Lipwig'),
    (34, 'Thud!',                                2005, 431, '0552152676', 'City Watch'),
    (35, 'Wintersmith',                          2006, 395, '0552553697', 'Tiffany Aching'),
    (36, 'Making Money',                         2007, 448, '0552154903', 'Moist von Lipwig'),
    (37, 'Unseen Academicals',                   2009, 533, '0552154911', 'Rincewind'),
    (38, 'I Shall Wear Midnight',                2010, 355, '0552555460', 'Tiffany Aching'),
    (39, 'Snuff',                                2011, 448, '0552166758', 'City Watch'),
    (40, 'Raising Steam',                        2013, 470, '0552170461', 'Moist von Lipwig'),
    (41, "The Shepherd's Crown",                 2015, 362, '0552566373', 'Tiffany Aching'),
]


with app.app_context():
    db.create_all()
    # SQLite-safe migrations: add columns if they don't exist (errors swallowed)
    for sql in [
        "ALTER TABLE book ADD COLUMN category VARCHAR(50) DEFAULT 'general'",
        "ALTER TABLE project ADD COLUMN priority VARCHAR(20) DEFAULT 'want'",
        "ALTER TABLE project ADD COLUMN effort VARCHAR(5) DEFAULT 'M'",
        "ALTER TABLE project ADD COLUMN percent_complete INTEGER DEFAULT 0",
        "ALTER TABLE project ADD COLUMN deadline DATE",
        "ALTER TABLE project ADD COLUMN tags VARCHAR(300) DEFAULT ''",
        "ALTER TABLE project ADD COLUMN is_archived BOOLEAN DEFAULT 0",
        "ALTER TABLE project ADD COLUMN created_at DATE",
        "ALTER TABLE project_task ADD COLUMN effort_minutes INTEGER DEFAULT 30",
        "ALTER TABLE project_task ADD COLUMN completed_at DATE",
        "ALTER TABLE book ADD COLUMN series VARCHAR(120) DEFAULT ''",
        "ALTER TABLE book ADD COLUMN subseries VARCHAR(120) DEFAULT ''",
        "ALTER TABLE book ADD COLUMN series_order INTEGER DEFAULT 0",
        "ALTER TABLE book ADD COLUMN publisher VARCHAR(120) DEFAULT ''",
        "ALTER TABLE book ADD COLUMN year INTEGER",
        "ALTER TABLE book ADD COLUMN isbn VARCHAR(20) DEFAULT ''",
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
        for name, icon, color, priority, effort, tasks in PROJECTS_SEED:
            p = Project(name=name, icon=icon, color=color,
                        priority=priority, effort=effort, created_at=date.today())
            db.session.add(p)
            db.session.flush()
            for t in tasks:
                db.session.add(ProjectTask(project_id=p.id, title=t, effort_minutes=45))
        db.session.commit()

    if Habit.query.count() == 0:
        for name, icon in HABITS_SEED:
            db.session.add(Habit(name=name, icon=icon))
        db.session.commit()

    # Discworld seed — only add books not already in the DB
    existing_titles = {b.title for b in Book.query.filter_by(series='Discworld').all()}
    for order, title, year, pages, isbn, subseries in DISCWORLD_SEED:
        if title in existing_titles:
            continue
        db.session.add(Book(
            title=title,
            author='Terry Pratchett',
            category='fiction',
            total_pages=pages,
            pages_read=0,
            cover_url=f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg',
            series='Discworld',
            subseries=subseries,
            series_order=order,
            publisher='Corgi',
            year=year,
            isbn=isbn,
            is_reading=False,
        ))
    db.session.commit()


# ── CALENDAR ───────────────────────────────────────────────────────────────

@app.route('/')
def root():
    return redirect(url_for('today_page'))

@app.route('/calendar')
def index():
    date_str = request.args.get('date')
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    start_of_week = target_date - timedelta(days=target_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    tasks = Task.query.filter(
        Task.date >= start_of_week, Task.date <= week_dates[-1]
    ).order_by(Task.is_completed, Task.time).all()
    books = {b.id: b for b in Book.query.all()}

    # Overlays: project deadlines in this week
    deadline_projects = Project.query.filter(
        Project.is_archived == False,
        Project.deadline >= start_of_week,
        Project.deadline <= week_dates[-1]
    ).all()
    deadlines_by_date = {}
    for p in deadline_projects:
        deadlines_by_date.setdefault(p.deadline, []).append(p)

    # Completed project tasks this week (overlay as ✓ markers)
    completed_tasks = ProjectTask.query.filter(
        ProjectTask.completed_at >= start_of_week,
        ProjectTask.completed_at <= week_dates[-1]
    ).all()
    completed_by_date = {}
    for t in completed_tasks:
        completed_by_date.setdefault(t.completed_at, []).append(t)

    prev_week = (start_of_week - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (start_of_week + timedelta(days=7)).strftime('%Y-%m-%d')
    return render_template('calendar.html', tasks=tasks, week_dates=week_dates,
                           prev_week=prev_week, next_week=next_week,
                           current_week=date.today().strftime('%Y-%m-%d'),
                           books=books, today=date.today(), active='calendar',
                           deadlines_by_date=deadlines_by_date,
                           completed_by_date=completed_by_date,
                           priority_info=PRIORITY_INFO)

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


# ── DESIGN DIARY ────────────────────────────────────────────────────────────

@app.route('/diary')
def diary_page():
    date_str = request.args.get('date')
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    start_of_week = target_date - timedelta(days=target_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    entries = {e.date: e for e in DiaryEntry.query.filter(
        DiaryEntry.date >= start_of_week, DiaryEntry.date <= week_dates[-1]).all()}
    images_by_date = {}
    for img in DiaryImage.query.filter(
        DiaryImage.date >= start_of_week, DiaryImage.date <= week_dates[-1]).all():
        images_by_date.setdefault(img.date, []).append(img)
    prev_week = (start_of_week - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (start_of_week + timedelta(days=7)).strftime('%Y-%m-%d')
    return render_template('diary.html', week_dates=week_dates, entries=entries,
                           images_by_date=images_by_date, prev_week=prev_week,
                           next_week=next_week, current_week=date.today().strftime('%Y-%m-%d'),
                           today=date.today(), active='diary')

@app.route('/diary/save/<date_str>', methods=['POST'])
def save_diary_entry(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d').date()
    entry = DiaryEntry.query.filter_by(date=d).first()
    if not entry:
        entry = DiaryEntry(date=d)
        db.session.add(entry)
    def gi(k):
        v = request.form.get(k)
        return int(v) if v and v.isdigit() else None
    entry.felt_pressure = gi('felt_pressure')
    entry.workload = gi('workload')
    entry.direction_clarity = gi('direction_clarity')
    entry.design_vision = gi('design_vision')
    entry.design_satisfaction = gi('design_satisfaction')
    entry.notes = request.form.get('notes', '')
    db.session.commit()
    return redirect(url_for('diary_page', date=date_str) + '#day-' + date_str)


@app.route('/diary/upload/<date_str>', methods=['POST'])
def upload_diary_image(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d').date()
    f = request.files.get('image')
    if f and f.filename:
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        filename = f"{date_str}_{uuid.uuid4().hex[:8]}{ext}"
        f.save(os.path.join(UPLOAD_FOLDER, filename))
        db.session.add(DiaryImage(
            date=d, filename=filename,
            method=request.form.get('method', ''),
            intent=request.form.get('intent', ''),
            insight=request.form.get('insight', ''),
        ))
        db.session.commit()
    return redirect(url_for('diary_page', date=date_str) + '#day-' + date_str)

@app.route('/diary/image/update/<int:id>', methods=['POST'])
def update_diary_image(id):
    img = DiaryImage.query.get_or_404(id)
    img.method = request.form.get('method', '')
    img.intent = request.form.get('intent', '')
    img.insight = request.form.get('insight', '')
    db.session.commit()
    return redirect(request.referrer or url_for('diary_page'))

@app.route('/diary/image/delete/<int:id>')
def delete_diary_image(id):
    img = DiaryImage.query.get_or_404(id)
    path = os.path.join(UPLOAD_FOLDER, img.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(img)
    db.session.commit()
    return redirect(request.referrer or url_for('diary_page'))


# Spin

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


# Stats

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

    # ── New Phase 4 metrics ──
    # Productivity heatmap (from ProjectTask.completed_at, last 90 days)
    ninety_ago = today - timedelta(days=89)
    completion_map = {}
    for t in ProjectTask.query.filter(ProjectTask.completed_at >= ninety_ago).all():
        k = t.completed_at.isoformat()
        completion_map[k] = completion_map.get(k, 0) + 1
    productivity_heatmap = []
    for i in range(89, -1, -1):
        d = today - timedelta(days=i)
        n = completion_map.get(d.isoformat(), 0)
        intensity = 0 if n == 0 else 1 if n < 2 else 2 if n < 4 else 3 if n < 7 else 4
        productivity_heatmap.append({'date': d, 'count': n, 'intensity': intensity})

    # Projects by priority
    all_projects = Project.query.filter_by(is_archived=False).all()
    priority_breakdown = {key: {'total': 0, 'done': 0, 'pct': 0} for key in PRIORITY_ORDER}
    for p in all_projects:
        b = priority_breakdown.setdefault(p.priority, {'total': 0, 'done': 0, 'pct': 0})
        b['total'] += 1
        if p.computed_percent >= 100:
            b['done'] += 1
    for b in priority_breakdown.values():
        b['pct'] = int(round(b['done'] / b['total'] * 100)) if b['total'] else 0

    # Book reading progress
    all_books = Book.query.all()
    books_total = len(all_books)
    books_finished = sum(1 for b in all_books if b.is_finished)
    books_reading = sum(1 for b in all_books if b.is_reading)
    total_pages_read = sum(b.pages_read for b in all_books)

    # Library coverage by series
    series_coverage = {}
    for b in all_books:
        if not b.series:
            continue
        s = series_coverage.setdefault(b.series, {'total': 0, 'finished': 0})
        s['total'] += 1
        if b.is_finished:
            s['finished'] += 1
    for s in series_coverage.values():
        s['pct'] = int(round(s['finished'] / s['total'] * 100)) if s['total'] else 0
    series_coverage = dict(sorted(series_coverage.items(), key=lambda x: -x[1]['total']))

    # Mood/energy avg over last 30 days
    recent_logs = DailyLog.query.filter(DailyLog.date >= thirty_ago).all()
    mood_30 = [l.mood for l in recent_logs if l.mood]
    energy_30 = [l.energy for l in recent_logs if l.energy]
    mood_30_avg = round(sum(mood_30) / len(mood_30), 1) if mood_30 else None
    energy_30_avg = round(sum(energy_30) / len(energy_30), 1) if energy_30 else None

    # Reward totals (all-time + this month)
    month_start = today.replace(day=1)
    rewards_all = RewardLog.query.filter_by(earned=True).count()
    rewards_month = RewardLog.query.filter(
        RewardLog.earned == True,
        RewardLog.date >= month_start
    ).count()

    # Longest project task streak (consecutive days with at least one completed task)
    completed_days = sorted({t.completed_at for t in ProjectTask.query.filter(
        ProjectTask.completed_at.isnot(None)).all()})
    longest_streak = 0
    current_run = 0
    prev = None
    for d in completed_days:
        if prev and (d - prev).days == 1:
            current_run += 1
        else:
            current_run = 1
        prev = d
        longest_streak = max(longest_streak, current_run)

    # Current streak (already used in today_page logic)
    current_streak = 0
    check = today
    while ProjectTask.query.filter_by(completed_at=check).count() > 0:
        current_streak += 1
        check -= timedelta(days=1)

    # Media collection totals
    movie_total = Movie.query.count()
    movie_watched = Movie.query.filter_by(status='watched').count()
    boardgame_total = Boardgame.query.filter_by(is_in_collection=True).count()
    total_plays = sum(g.times_played for g in Boardgame.query.all())

    return render_template('stats.html',
                           books_total=books_total,
                           books_finished=books_finished,
                           books_reading=books_reading,
                           total_pages_read=total_pages_read,
                           series_coverage=series_coverage,
                           anime_total=Anime.query.count(),
                           manga_total=Manga.query.count(),
                           movie_total=movie_total,
                           movie_watched=movie_watched,
                           boardgame_total=boardgame_total,
                           total_plays=total_plays,
                           category_hours=category_hours,
                           top_skill=top_skill,
                           total_skill_hours=total_skill_hours,
                           heatmap=heatmap,
                           productivity_heatmap=productivity_heatmap,
                           priority_breakdown=priority_breakdown,
                           priority_order=PRIORITY_ORDER,
                           priority_info=PRIORITY_INFO,
                           mood_30_avg=mood_30_avg,
                           energy_30_avg=energy_30_avg,
                           rewards_all=rewards_all,
                           rewards_month=rewards_month,
                           current_streak=current_streak,
                           longest_streak=longest_streak,
                           habit_streaks=habit_streaks,
                           active='stats')


# Priority info and recommendation engine

PRIORITY_INFO = {
    'must': {'label': 'Must do',    'icon': '🔥', 'color': '#c1432e', 'weight': 100},
    'have': {'label': 'Have to do', 'icon': '⚡',     'color': '#e08e3c', 'weight': 60},
    'want': {'label': 'Want to do', 'icon': '💡', 'color': '#d4a373', 'weight': 30},
    'fun':  {'label': 'Is fun',     'icon': '🎮', 'color': '#7a9b76', 'weight': 15},
}
PRIORITY_ORDER = ['must', 'have', 'want', 'fun']

MODE_INFO = {
    'locked':   {'label': '🔒 Locked-in',          'desc': 'Pure focus. Must + Have only.'},
    'reward':   {'label': '🎁 Productive + reward','desc': 'Work first, fun task at the end.'},
    'fun':      {'label': '🎉 Pure fun',           'desc': 'Just the fun stuff today.'},
    'balanced': {'label': '⚖️ Balanced',        'desc': 'Mix of priorities, interleaved.'},
}


def score_task(task, project, today):
    if task.is_completed:
        return -1
    pinfo = PRIORITY_INFO.get(project.priority, PRIORITY_INFO['want'])
    score = pinfo['weight']
    if project.computed_percent >= 75:
        score += 40
    elif project.computed_percent >= 50:
        score += 15
    if project.deadline:
        days = (project.deadline - today).days
        if days < 0:
            score += 80
        elif days <= 3:
            score += 50
        elif days <= 7:
            score += 25
        elif days <= 14:
            score += 10
    if task.calendar_date == today:
        score += 30
    return score


def recommend_tasks(free_minutes, mode, today):
    projects = Project.query.filter_by(is_archived=False).all()
    allowed = set(PRIORITY_ORDER)
    if mode == 'locked':
        allowed = {'must', 'have'}
    elif mode == 'fun':
        allowed = {'fun'}
    candidates = []
    for p in projects:
        if p.priority not in allowed:
            continue
        for t in p.tasks:
            if t.is_completed:
                continue
            s = score_task(t, p, today)
            candidates.append((t, p, s, t.effort_minutes or 30))
    candidates.sort(key=lambda x: -x[2])
    picked, used = [], 0
    for tup in candidates:
        t, p, s, mins = tup
        if used + mins <= free_minutes + 10:
            picked.append(tup)
            used += mins
        if used >= free_minutes:
            break
    if mode == 'reward':
        fun_cand = [(t, p, score_task(t, p, today), t.effort_minutes or 30)
                    for p in projects if p.priority == 'fun'
                    for t in p.tasks if not t.is_completed]
        fun_cand.sort(key=lambda x: -x[2])
        if fun_cand and not any(c[1].priority == 'fun' for c in picked):
            picked.append(fun_cand[0])
    if mode == 'balanced':
        if not any(c[1].priority == 'fun' for c in picked):
            fun_cand = [(t, p, score_task(t, p, today), t.effort_minutes or 30)
                        for p in projects if p.priority == 'fun'
                        for t in p.tasks if not t.is_completed]
            if fun_cand:
                picked.append(max(fun_cand, key=lambda x: x[2]))
    return picked


# Today page

@app.route('/today', methods=['GET', 'POST'])
def today_page():
    today = date.today()
    plan = DailyPlan.query.filter_by(date=today).first()

    if request.method == 'POST':
        if not plan:
            plan = DailyPlan(date=today)
            db.session.add(plan)
        plan.free_time_minutes = int(request.form.get('free_time_minutes', 180))
        plan.mode = request.form.get('mode', 'balanced')
        plan.notes = request.form.get('notes', '')
        suggestions = recommend_tasks(plan.free_time_minutes, plan.mode, today)
        plan.suggested_task_ids = ','.join(str(t.id) for t, _, _, _ in suggestions)
        db.session.commit()
        return redirect(url_for('today_page'))

    suggestions = []
    if plan and plan.suggested_task_ids:
        ids = [int(x) for x in plan.suggested_task_ids.split(',') if x]
        id_to_task = {t.id: t for t in ProjectTask.query.filter(ProjectTask.id.in_(ids)).all()}
        for tid in ids:
            t = id_to_task.get(tid)
            if t:
                suggestions.append((t, t.project, score_task(t, t.project, today),
                                    t.effort_minutes or 30))

    almost_done = [p for p in Project.query.filter_by(is_archived=False).all()
                   if 75 <= p.computed_percent < 100]
    almost_done.sort(key=lambda p: -p.computed_percent)

    streak = 0
    check = today
    while ProjectTask.query.filter_by(completed_at=check).count() > 0:
        streak += 1
        check -= timedelta(days=1)

    todays_wins = ProjectTask.query.filter_by(completed_at=today).all()
    daily_log = DailyLog.query.filter_by(date=today).first()
    total_suggested_minutes = sum(m for _, _, _, m in suggestions)
    reward_status = compute_reward_status(plan, today)

    return render_template('today.html',
                           active='today', today=today, plan=plan,
                           suggestions=suggestions, almost_done=almost_done,
                           streak=streak, todays_wins=todays_wins,
                           daily_log=daily_log,
                           total_suggested_minutes=total_suggested_minutes,
                           priority_info=PRIORITY_INFO, mode_info=MODE_INFO,
                           reward_status=reward_status)


@app.route('/today/log', methods=['POST'])
def save_daily_log():
    today = date.today()
    log = DailyLog.query.filter_by(date=today).first()
    if not log:
        log = DailyLog(date=today)
        db.session.add(log)
    def gi(k):
        v = request.form.get(k)
        return int(v) if v and v.isdigit() else None
    log.energy = gi('energy')
    log.mood = gi('mood')
    log.win = request.form.get('win', '')
    log.notes = request.form.get('notes', '')
    db.session.commit()
    return redirect(url_for('today_page'))


@app.route('/today/complete_task/<int:id>')
def complete_today_task(id):
    pt = ProjectTask.query.get_or_404(id)
    pt.is_completed = not pt.is_completed
    pt.completed_at = date.today() if pt.is_completed else None
    db.session.commit()
    return redirect(request.referrer or url_for('today_page'))


# ── WEEKLY REVIEW (Phase 4) ────────────────────────────────────────────────

@app.route('/review')
def review_page():
    today = date.today()
    try:
        week_offset = int(request.args.get('w', '0'))
    except ValueError:
        week_offset = 0
    start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end = start + timedelta(days=6)

    wins = ProjectTask.query.filter(
        ProjectTask.completed_at >= start,
        ProjectTask.completed_at <= end
    ).all()
    wins_by_project = {}
    for w in wins:
        if w.project:
            wins_by_project.setdefault(w.project.id, {'project': w.project, 'tasks': []})
            wins_by_project[w.project.id]['tasks'].append(w)

    time_per_project = []
    for entry in wins_by_project.values():
        mins = sum(t.effort_minutes or 30 for t in entry['tasks'])
        time_per_project.append({
            'project': entry['project'],
            'minutes': mins,
            'task_count': len(entry['tasks']),
        })
    time_per_project.sort(key=lambda x: -x['minutes'])
    total_minutes = sum(x['minutes'] for x in time_per_project)

    active_projects = Project.query.filter_by(is_archived=False).all()
    project_ids_with_wins = set(wins_by_project.keys())
    stalled = []
    for p in active_projects:
        if p.id in project_ids_with_wins:
            continue
        if any(not t.is_completed for t in p.tasks):
            stalled.append(p)
    stalled.sort(key=lambda p: -PRIORITY_INFO.get(p.priority, PRIORITY_INFO['want'])['weight'])

    logs = DailyLog.query.filter(DailyLog.date >= start, DailyLog.date <= end).all()
    logs_by_date = {l.date: l for l in logs}
    mood_values = [l.mood for l in logs if l.mood]
    energy_values = [l.energy for l in logs if l.energy]
    mood_avg = round(sum(mood_values) / len(mood_values), 1) if mood_values else None
    energy_avg = round(sum(energy_values) / len(energy_values), 1) if energy_values else None

    day_trends = []
    for i in range(7):
        d = start + timedelta(days=i)
        l = logs_by_date.get(d)
        day_trends.append({
            'date': d, 'label': d.strftime('%a'),
            'mood': l.mood if l else None,
            'energy': l.energy if l else None,
            'win': l.win if l else '',
        })

    movies_watched = Movie.query.filter(
        Movie.status == 'watched',
        Movie.watched_on >= start, Movie.watched_on <= end
    ).all()
    boardgame_plays = Boardgame.query.filter(
        Boardgame.last_played >= start, Boardgame.last_played <= end
    ).all()
    rewards = RewardLog.query.filter(
        RewardLog.date >= start, RewardLog.date <= end,
        RewardLog.earned == True
    ).all()

    reading_now = Book.query.filter_by(is_reading=True).first()
    watching_now = Series.query.filter_by(is_watching=True).first()

    return render_template('review.html',
                           active='review',
                           start=start, end=end, today=today,
                           week_offset=week_offset,
                           prev_offset=week_offset - 1,
                           next_offset=week_offset + 1,
                           wins=wins, wins_by_project=wins_by_project,
                           time_per_project=time_per_project,
                           total_minutes=total_minutes,
                           stalled=stalled,
                           mood_avg=mood_avg, energy_avg=energy_avg,
                           day_trends=day_trends,
                           movies_watched=movies_watched,
                           boardgame_plays=boardgame_plays,
                           rewards=rewards,
                           reading_now=reading_now, watching_now=watching_now,
                           priority_info=PRIORITY_INFO)


# Projects

@app.route('/projects')
def projects_page():
    projects = Project.query.filter_by(is_archived=False).all()
    by_priority = {p: [] for p in PRIORITY_ORDER}
    for proj in projects:
        by_priority.setdefault(proj.priority, []).append(proj)
    return render_template('projects.html',
                           active='projects', by_priority=by_priority,
                           priority_order=PRIORITY_ORDER,
                           priority_info=PRIORITY_INFO, today=date.today())


@app.route('/projects/create', methods=['POST'])
def create_project():
    deadline_str = request.form.get('deadline', '').strip()
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    p = Project(
        name=request.form['name'],
        icon=request.form.get('icon', '📁') or '📁',
        color=request.form.get('color', '#d4a373'),
        description=request.form.get('description', ''),
        priority=request.form.get('priority', 'want'),
        effort=request.form.get('effort', 'M'),
        deadline=deadline,
        tags=request.form.get('tags', ''),
        created_at=date.today(),
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('projects_page'))


@app.route('/projects/<int:id>/update', methods=['POST'])
def update_project(id):
    p = Project.query.get_or_404(id)
    p.name = request.form.get('name', p.name)
    p.priority = request.form.get('priority', p.priority)
    p.icon = request.form.get('icon', p.icon) or '📁'
    p.color = request.form.get('color', p.color)
    p.description = request.form.get('description', p.description)
    p.tags = request.form.get('tags', p.tags)
    p.percent_complete = int(request.form.get('percent_complete', p.percent_complete or 0))
    deadline_str = request.form.get('deadline', '').strip()
    p.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    db.session.commit()
    return redirect(request.referrer or url_for('projects_page'))


@app.route('/projects/<int:id>/archive')
def archive_project(id):
    p = Project.query.get_or_404(id)
    p.is_archived = not p.is_archived
    db.session.commit()
    return redirect(url_for('projects_page'))


@app.route('/projects/<int:pid>/task/quick_add', methods=['POST'])
def quick_add_project_task(pid):
    Project.query.get_or_404(pid)
    title = request.form.get('title', '').strip()
    if title:
        effort = int(request.form.get('effort_minutes', 30) or 30)
        db.session.add(ProjectTask(project_id=pid, title=title, effort_minutes=effort))
        db.session.commit()
    return redirect(request.referrer or url_for('projects_page'))


# Library hub

@app.route('/bookcase')
def fullscreen_bookcase():
    all_books = Book.query.order_by(Book.series_order, Book.title).all()
    shelves = {}
    for b in all_books:
        series_key = b.series or 'Unsorted'
        sub_key = b.subseries or '—'
        shelves.setdefault(series_key, {}).setdefault(sub_key, []).append(b)
    return render_template('bookcase.html',
                           shelves=shelves,
                           total_books=len(all_books),
                           finished_books=sum(1 for b in all_books if b.is_finished),
                           reading_count=sum(1 for b in all_books if b.is_reading))


@app.route('/library')
@app.route('/library/<tab>')
def library_page(tab='books'):
    if tab not in ('books', 'movies', 'series', 'boardgames', 'manga', 'anime'):
        tab = 'books'
    ctx = {'active': 'library', 'tab': tab}
    if tab == 'books':
        ctx['current'] = Book.query.filter_by(is_reading=True).first()
        ctx['items'] = Book.query.filter_by(is_reading=False).all()
        all_books = Book.query.order_by(Book.series_order, Book.title).all()
        shelves = {}
        for b in all_books:
            series_key = b.series or 'Unsorted'
            sub_key = b.subseries or '—'
            shelves.setdefault(series_key, {}).setdefault(sub_key, []).append(b)
        ctx['shelves'] = shelves
        ctx['total_books'] = len(all_books)
        ctx['finished_books'] = sum(1 for b in all_books if b.is_finished)
    elif tab == 'movies':
        ctx['watchlist'] = Movie.query.filter_by(status='watchlist').all()
        ctx['watched'] = Movie.query.filter_by(status='watched').order_by(Movie.watched_on.desc()).all()
    elif tab == 'series':
        ctx['current'] = Series.query.filter_by(is_watching=True).first()
        ctx['items'] = Series.query.filter_by(is_watching=False).all()
    elif tab == 'boardgames':
        ctx['collection'] = Boardgame.query.filter_by(is_in_collection=True).order_by(Boardgame.title).all()
        ctx['wishlist'] = Boardgame.query.filter_by(is_in_collection=False).all()
    elif tab == 'manga':
        ctx['current'] = Manga.query.filter_by(is_reading=True).first()
        ctx['items'] = Manga.query.filter_by(is_reading=False).all()
    elif tab == 'anime':
        ctx['current'] = Anime.query.filter_by(is_watching=True).first()
        ctx['items'] = Anime.query.filter_by(is_watching=False).all()
    return render_template('library.html', **ctx)


# Movies

@app.route('/movies/add', methods=['POST'])
def add_movie():
    db.session.add(Movie(
        title=request.form['title'],
        year=int(request.form['year']) if request.form.get('year') else None,
        runtime=int(request.form.get('runtime', 120) or 120),
        cover_url=request.form.get('cover_url', ''),
        status=request.form.get('status', 'watchlist'),
    ))
    db.session.commit()
    return redirect(url_for('library_page', tab='movies'))


@app.route('/movies/<int:id>/watched', methods=['POST'])
def mark_movie_watched(id):
    m = Movie.query.get_or_404(id)
    m.status = 'watched'
    m.watched_on = date.today()
    rating = request.form.get('rating')
    if rating and rating.isdigit():
        m.rating = int(rating)
    db.session.commit()
    return redirect(url_for('library_page', tab='movies'))


@app.route('/movies/<int:id>/delete')
def delete_movie(id):
    db.session.delete(Movie.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('library_page', tab='movies'))


# Series

@app.route('/series/add', methods=['POST'])
def add_series():
    db.session.add(Series(
        title=request.form['title'],
        total_episodes=int(request.form.get('total_episodes', 10) or 10),
        total_seasons=int(request.form.get('total_seasons', 1) or 1),
        cover_url=request.form.get('cover_url', ''),
        is_watching=Series.query.filter_by(is_watching=True).count() == 0,
    ))
    db.session.commit()
    return redirect(url_for('library_page', tab='series'))


@app.route('/series/<int:id>/progress', methods=['POST'])
def update_series_progress(id):
    s = Series.query.get_or_404(id)
    s.episodes_watched = min(int(request.form.get('episodes_watched', 0)), s.total_episodes)
    if s.episodes_watched >= s.total_episodes:
        s.is_watching = False
    db.session.commit()
    return redirect(url_for('library_page', tab='series'))


@app.route('/series/<int:id>/watching')
def set_watching_series(id):
    Series.query.filter_by(is_watching=True).update({'is_watching': False})
    Series.query.get_or_404(id).is_watching = True
    db.session.commit()
    return redirect(url_for('library_page', tab='series'))


@app.route('/series/<int:id>/delete')
def delete_series(id):
    db.session.delete(Series.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('library_page', tab='series'))


# Boardgames

@app.route('/boardgames/add', methods=['POST'])
def add_boardgame():
    db.session.add(Boardgame(
        title=request.form['title'],
        min_players=int(request.form.get('min_players', 2) or 2),
        max_players=int(request.form.get('max_players', 4) or 4),
        avg_playtime=int(request.form.get('avg_playtime', 60) or 60),
        cover_url=request.form.get('cover_url', ''),
        is_in_collection=request.form.get('in_collection', 'on') == 'on',
    ))
    db.session.commit()
    return redirect(url_for('library_page', tab='boardgames'))


@app.route('/boardgames/<int:id>/play')
def log_boardgame_play(id):
    bg = Boardgame.query.get_or_404(id)
    bg.times_played += 1
    bg.last_played = date.today()
    db.session.commit()
    return redirect(url_for('library_page', tab='boardgames'))


@app.route('/boardgames/<int:id>/delete')
def delete_boardgame(id):
    db.session.delete(Boardgame.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('library_page', tab='boardgames'))


# ââ QUICK CAPTURE (Phase 3) ââââââââââââââââââââââââââââââââââââââââââââââââ

@app.route('/capture', methods=['POST'])
def quick_capture():
    text = request.form.get('text', '').strip()
    capture_type = request.form.get('type', 'project')
    if not text:
        return redirect(request.referrer or url_for('today_page'))
    if capture_type == 'book':
        db.session.add(Book(title=text, author='', total_pages=300,
                            category='general', is_reading=False))
    elif capture_type == 'movie':
        db.session.add(Movie(title=text, runtime=120, status='watchlist'))
    elif capture_type == 'task':
        inbox = Project.query.filter_by(name='Inbox').first()
        if not inbox:
            inbox = Project(name='Inbox', icon='📥', color='#9c6644',
                            priority='want', effort='S', created_at=date.today())
            db.session.add(inbox)
            db.session.flush()
        db.session.add(ProjectTask(project_id=inbox.id, title=text, effort_minutes=30))
    elif capture_type == 'fun':
        db.session.add(Project(name=text, icon='🎮', color='#7a9b76',
                               priority='fun', effort='S', created_at=date.today()))
    else:
        db.session.add(Project(name=text, icon='📁', color='#d4a373',
                               priority='want', effort='M', created_at=date.today()))
    db.session.commit()
    return redirect(request.referrer or url_for('today_page'))


# ââ REWARD BANK (Phase 3) ââââââââââââââââââââââââââââââââââââââââââââââââââ

def compute_reward_status(plan, today):
    if not plan or plan.mode != 'reward' or not plan.suggested_task_ids:
        return None
    ids = [int(x) for x in plan.suggested_task_ids.split(',') if x]
    if not ids:
        return None
    tasks = ProjectTask.query.filter(ProjectTask.id.in_(ids)).all()
    required = [t for t in tasks if t.project and t.project.priority != 'fun']
    reward_tasks = [t for t in tasks if t.project and t.project.priority == 'fun']
    required_done = sum(1 for t in required if t.is_completed)
    required_total = len(required)
    unlocked = required_total > 0 and required_done >= required_total
    reward_task = reward_tasks[0] if reward_tasks else None
    return {
        'required_done': required_done,
        'required_total': required_total,
        'unlocked': unlocked,
        'reward_task': reward_task,
        'reward_project': reward_task.project if reward_task else None,
    }


@app.route('/reward/claim/<int:task_id>')
def claim_reward(task_id):
    pt = ProjectTask.query.get_or_404(task_id)
    log = RewardLog(date=date.today(),
                    reward_description=f"{pt.project.name}: {pt.title}",
                    earned=True)
    db.session.add(log)
    db.session.commit()
    return redirect(url_for('today_page'))


# ââ BACKLOG ROULETTE (Phase 3) âââââââââââââââââââââââââââââââââââââââââââââ

@app.route('/spin/<category>')
def spin_category(category):
    pick = None
    if category == 'fun':
        fun_projects = Project.query.filter_by(priority='fun', is_archived=False).all()
        candidates = [(t, p) for p in fun_projects for t in p.tasks if not t.is_completed]
        if candidates:
            t, p = random.choice(candidates)
            pick = {'kind': 'fun_task', 'icon': '🎮', 'title': t.title,
                    'subtitle': p.name, 'task_id': t.id}
    elif category == 'want':
        want_projects = Project.query.filter_by(priority='want', is_archived=False).all()
        candidates = [(t, p) for p in want_projects for t in p.tasks if not t.is_completed]
        if candidates:
            t, p = random.choice(candidates)
            pick = {'kind': 'want_task', 'icon': '💡', 'title': t.title,
                    'subtitle': p.name, 'task_id': t.id}
    elif category == 'book':
        books = Book.query.filter(Book.pages_read == 0).all()
        if books:
            b = random.choice(books)
            pick = {'kind': 'book', 'icon': '📚', 'title': b.title,
                    'subtitle': b.author or 'Unknown', 'book_id': b.id}
    elif category == 'movie':
        movies = Movie.query.filter_by(status='watchlist').all()
        if movies:
            m = random.choice(movies)
            pick = {'kind': 'movie', 'icon': '🎬', 'title': m.title,
                    'subtitle': str(m.year) if m.year else '', 'movie_id': m.id}
    elif category == 'boardgame':
        games = Boardgame.query.filter_by(is_in_collection=True).all()
        if games:
            g = random.choice(games)
            pick = {'kind': 'boardgame', 'icon': '🎲', 'title': g.title,
                    'subtitle': f"{g.min_players}-{g.max_players} players · {g.avg_playtime}m",
                    'boardgame_id': g.id}
    return render_template('spin_result.html', pick=pick, category=category, active='spin')


@app.route('/sw.js')
def service_worker():
    resp = make_response(send_from_directory('static', 'sw.js'))
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Content-Type'] = 'application/javascript'
    return resp


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true')
