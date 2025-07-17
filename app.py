from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import date, datetime
from collections import Counter

app = Flask(__name__)
app.secret_key = '1916'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # <-- This line is required

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default="Medium")
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

@app.route('/', methods=['GET'])
def index():
    priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
    # Filtering, sorting, and search
    status = request.args.get('status', 'all')
    sort = request.args.get('sort', 'priority')
    search = request.args.get('search', '').strip()
    query = Task.query
    if status == 'completed':
        query = query.filter_by(completed=True)
    elif status == 'pending':
        query = query.filter_by(completed=False)
    if search:
        query = query.filter(Task.task.ilike(f'%{search}%'))
    if sort == 'priority':
        tasks = sorted(query.all(), key=lambda t: (priority_order[t.priority], t.completed))
    elif sort == 'due_date':
        tasks = sorted(query.all(), key=lambda t: (t.due_date or '9999-12-31', t.completed))
    elif sort == 'created':
        tasks = sorted(query.all(), key=lambda t: t.id)
    else:
        tasks = query.all()
    completed_count = sum(1 for t in tasks if t.completed)
    percent = int((completed_count / len(tasks)) * 100) if tasks else 0
    return render_template('index.html', tasks=tasks, percent=percent, status=status, sort=sort, search=search, today=date.today())


@app.route('/add', methods=['POST'])
def add():
    task_content = request.form['task']
    priority = request.form['priority']
    due_date = request.form.get('due_date')
    if due_date:
        due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
    else:
        due_date = None
    if task_content:
        new_task = Task(task=task_content, priority=priority, due_date=due_date, created_at=datetime.utcnow())
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('index'))



@app.route('/complete/<int:id>')
def complete(id):
    task = Task.query.get_or_404(id)
    task.completed = not task.completed
    if task.completed:
        task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit(task_id):
    task = Task.query.get_or_404(task_id)

    if request.method == 'POST':
        task.task = request.form['task']
        task.priority = request.form['priority']  # ✅ Make sure this line is present
        due_date = request.form.get('due_date')
        if due_date:
            from datetime import datetime
            task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        else:
            task.due_date = None
        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('edit.html', task=task)
@app.route('/dashboard')
def dashboard():
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(completed=True).count()
    incomplete_tasks = total_tasks - completed_tasks

    # Priority distribution
    priorities = ['High', 'Medium', 'Low']
    priority_data = {
        priority: Task.query.filter_by(priority=priority).count()
        for priority in priorities
    }

    # --- Progress Analytics ---
    # 1. Completions per day (last 7 days)
    from datetime import timedelta
    today = date.today()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    completions = Task.query.filter(Task.completed_at != None).all()
    completions_per_day = Counter(
        (t.completed_at.date() for t in completions if t.completed_at)
    )
    completions_chart = [completions_per_day.get(day, 0) for day in last_7_days]
    completions_labels = [day.strftime('%a') for day in last_7_days]

    # 2. Completion rate
    completion_rate = int((completed_tasks / total_tasks) * 100) if total_tasks else 0

    # 3. Streak (consecutive days with at least one completion)
    streak = 0
    for day in reversed(last_7_days):
        if completions_per_day.get(day, 0) > 0:
            streak += 1
        else:
            break

    # 4. Average completion time (in hours)
    completion_times = [
        (t.completed_at - t.created_at).total_seconds() / 3600
        for t in completions if t.completed_at and t.created_at
    ]
    avg_completion_time = round(sum(completion_times) / len(completion_times), 1) if completion_times else None

    return render_template(
        'dashboard.html',
        total=total_tasks,
        completed=completed_tasks,
        incomplete=incomplete_tasks,
        priority_data=priority_data,
        completions_chart=completions_chart,
        completions_labels=completions_labels,
        completion_rate=completion_rate,
        streak=streak,
        avg_completion_time=avg_completion_time
    )

if __name__ == '__main__':
    if not os.path.exists('todo.db'):
        with app.app_context():
            db.create_all()

    import os
    port = int(os.environ.get('PORT', 5000))  # fallback to 5000 locally
    app.run(host='0.0.0.0', port=port)