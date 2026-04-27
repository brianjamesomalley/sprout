
Brian Omalley
10:16 AM (0 minutes ago)
to me

# sprout_revealed_preference.py
from flask import Flask, session, request, jsonify, render_template_string
from datetime import datetime, timedelta
import sqlite3
import json
import random
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "sprout-gentle-forest-2025"

# ----- Database setup -----
def init_db():
conn = sqlite3.connect('sprout.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
(id INTEGER PRIMARY KEY,
avatar_type TEXT,
accessories TEXT,
created_at TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS transactions
(id INTEGER PRIMARY KEY,
user_id INTEGER,
amount REAL,
category TEXT,
day_of_week INTEGER,
hour INTEGER,
timestamp TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS productivity_logs
(id INTEGER PRIMARY KEY,
user_id INTEGER,
date TEXT,
energy_level INTEGER,
tasks_completed INTEGER,
notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS revealed_patterns
(id INTEGER PRIMARY KEY,
user_id INTEGER,
pattern_type TEXT,
confidence REAL,
first_detected TIMESTAMP,
last_updated TIMESTAMP)''')
conn.commit()
conn.close()

init_db()

# ----- Avatar states (Blooket-style) -----
AVATAR_SPECIES = {
"axolotl": {"base_emoji": "🦎", "default_accessories": ["gills"]},
"frog": {"base_emoji": "🐸", "default_accessories": []},
"cat": {"base_emoji": "🐱", "default_accessories": ["whiskers"]},
"blob": {"base_emoji": "🫧", "default_accessories": []}
}

ACCESSORIES = {
"backpack": "🎒", # regular savings / ATM habit
"raincoat": "🧥", # spending on low-energy/rainy days
"party_hat": "🎉", # social spending detected
"sleepy_eyes": "😴", # low productivity detected
"sunglasses": "😎", # confidence / high energy
"tiny_umbrella": "☂️", # preparing for known triggers
"coffee": "☕", # morning spender
"moon": "🌙" # late-night activity
}

# ----- Pattern detection engine (the "whisper layer") -----
class SproutRevealedPreference:
def __init__(self, user_id):
self.user_id = user_id
self.conn = sqlite3.connect('sprout.db')
self.c = self.conn.cursor()

def log_transaction(self, amount, category, hour, day_of_week):
self.c.execute("""INSERT INTO transactions
(user_id, amount, category, hour, day_of_week, timestamp)
VALUES (?, ?, ?, ?, ?, ?)""",
(self.user_id, amount, category, hour, day_of_week, datetime.now()))
self.conn.commit()
self._detect_patterns()

def log_productivity(self, energy_level, tasks_completed):
today = datetime.now().date().isoformat()
self.c.execute("""INSERT OR REPLACE INTO productivity_logs
(user_id, date, energy_level, tasks_completed, notes)
VALUES (?, ?, ?, ?, ?)""",
(self.user_id, today, energy_level, tasks_completed, ""))
self.conn.commit()
self._detect_patterns()

def _detect_patterns(self):
"""The secret sauce — finds patterns without telling user unless asked"""

# Pattern 1: Friday ATM habit (specific day + cash withdrawal)
self.c.execute("""SELECT day_of_week, COUNT(*), AVG(amount)
FROM transactions
WHERE user_id = ? AND category = 'atm_withdrawal'
GROUP BY day_of_week""", (self.user_id,))
atm_patterns = self.c.fetchall()
for dow, count, avg_amount in atm_patterns:
if count >= 3 and avg_amount > 50:
self._save_pattern("friday_atm_habit", 0.7 + (count * 0.05),
{"day": dow, "avg_amount": avg_amount})

# Pattern 2: Low productivity → next-day spending spike
self.c.execute("""SELECT p.date, SUM(t.amount)
FROM productivity_logs p
JOIN transactions t ON date(t.timestamp) = date(p.date, '+1 day')
WHERE p.user_id = ? AND p.energy_level < 4
GROUP BY p.date""", (self.user_id,))
recovery_spending = self.c.fetchall()
if len(recovery_spending) >= 2:
self._save_pattern("low_energy_recovery_spending", 0.65,
{"avg_next_day_spend": sum(r[1] for r in recovery_spending)/len(recovery_spending)})

# Pattern 3: Social spending (weekend nights)
self.c.execute("""SELECT hour, AVG(amount)
FROM transactions
WHERE user_id = ? AND (day_of_week IN (5,6) AND hour > 18)
GROUP BY hour""", (self.user_id,))
social_spending = self.c.fetchall()
if social_spending and any(amt > 25 for _, amt in social_spending):
self._save_pattern("social_evening_spending", 0.8,
{"peak_hour": max(social_spending, key=lambda x: x[1])[0]})

# Pattern 4: Productivity cycles
self.c.execute("""SELECT strftime('%H', timestamp) as hour, AVG(energy_level)
FROM productivity_logs p
JOIN transactions t ON date(t.timestamp) = p.date
WHERE p.user_id = ?
GROUP BY hour
HAVING COUNT(*) > 1""", (self.user_id,))
energy_by_hour = self.c.fetchall()
if energy_by_hour:
best_hour = max(energy_by_hour, key=lambda x: x[1])[0]
worst_hour = min(energy_by_hour, key=lambda x: x[1])[0]
self._save_pattern("productivity_cycle", 0.75,
{"peak_hour": best_hour, "trough_hour": worst_hour})

def _save_pattern(self, pattern_type, confidence, details):
"""Store detected pattern with confidence score"""
self.c.execute("""INSERT OR REPLACE INTO revealed_patterns
(user_id, pattern_type, confidence, first_detected, last_updated, details)
VALUES (?, ?, ?, COALESCE((SELECT first_detected FROM revealed_patterns
WHERE user_id = ? AND pattern_type = ?), ?),
?, ?)""",
(self.user_id, pattern_type, confidence,
self.user_id, pattern_type, datetime.now(),
datetime.now(), json.dumps(details)))
self.conn.commit()

def get_active_accessories(self):
"""Determine what avatar accessories to show based on detected patterns"""
accessories = []

# Check for Friday ATM habit
self.c.execute("""SELECT confidence, details FROM revealed_patterns
WHERE user_id = ? AND pattern_type = 'friday_atm_habit'
AND confidence > 0.65""", (self.user_id,))
atm = self.c.fetchone()
if atm and datetime.now().weekday() == 4: # Friday
accessories.append("backpack")
if random.random() < 0.4: # subtle variation
accessories.append("tiny_umbrella")

# Check for low energy recovery spending
self.c.execute("""SELECT confidence FROM revealed_patterns
WHERE user_id = ? AND pattern_type = 'low_energy_recovery_spending'
AND confidence > 0.6""", (self.user_id,))
low_energy = self.c.fetchone()
if low_energy:
# Check if yesterday was low energy
yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
self.c.execute("SELECT energy_level FROM productivity_logs WHERE user_id = ? AND date = ?",
(self.user_id, yesterday))
energy = self.c.fetchone()
if energy and energy[0] < 4:
accessories.append("sleepy_eyes")
accessories.append("coffee")

# Check for social spending (today is Friday or Saturday)
if datetime.now().weekday() in [4, 5]:
self.c.execute("""SELECT confidence FROM revealed_patterns
WHERE user_id = ? AND pattern_type = 'social_evening_spending'
AND confidence > 0.7""", (self.user_id,))
social = self.c.fetchone()
if social:
accessories.append("party_hat")
if datetime.now().hour > 18:
accessories.append("sunglasses")

# Remove duplicates and return
return list(set(accessories))

def get_pattern_insight(self, pattern_type):
"""User asks 'why?' — gentle reveal"""
self.c.execute("""SELECT confidence, details, first_detected FROM revealed_patterns
WHERE user_id = ? AND pattern_type = ?
ORDER BY confidence DESC LIMIT 1""", (self.user_id, pattern_type))
result = self.c.fetchone()
if not result:
return None

confidence, details_json, first_detected = result
details = json.loads(details_json)

insights = {
"friday_atm_habit": f"I noticed you've taken cash out on Fridays {int(confidence*100)}% of the time — around ${details.get('avg_amount', 80)}. Want to plan for that?",
"low_energy_recovery_spending": f"On days after you feel low energy, you tend to spend about ${details.get('avg_next_day_spend', 35)}. That's not bad — just a pattern.",
"social_evening_spending": f"Your evenings out (around {details.get('peak_hour', 20)}:00) tend to cost a bit more. Worth knowing?",
"productivity_cycle": f"You're most energetic around {details.get('peak_hour', 10)}:00 and lowest around {details.get('trough_hour', 14)}:00. I can help you plan around that."
}

return insights.get(pattern_type, f"I spotted a pattern: {pattern_type}. Want to explore it together?")

def close(self):
self.conn.close()

# ----- Flask routes -----
@app.route('/')
def index():
return render_template_string(HTML_TEMPLATE)

@app.route('/api/avatar/choose', methods=['POST'])
def choose_avatar():
data = request.json
session['avatar_type'] = data.get('type', 'axolotl')
return jsonify({"status": "ok", "avatar": session['avatar_type']})

@app.route('/api/avatar/state')
def avatar_state():
user_id = session.get('user_id', 1) # simplified for demo
sprout = SproutRevealedPreference(user_id)
accessories = sprout.get_active_accessories()
sprout.close()

avatar_type = session.get('avatar_type', 'axolotl')
emoji = AVATAR_SPECIES[avatar_type]["base_emoji"]

accessory_emojis = [ACCESSORIES.get(a, "") for a in accessories if a in ACCESSORIES]

return jsonify({
"species": avatar_type,
"emoji": emoji,
"accessories": accessories,
"display": f"{emoji} {' '.join(accessory_emojis)}" if accessory_emojis else emoji,
"count": len(accessories)
})

@app.route('/api/spend', methods=['POST'])
def log_spend():
data = request.json
user_id = session.get('user_id', 1)
sprout = SproutRevealedPreference(user_id)
sprout.log_transaction(
amount=data['amount'],
category=data.get('category', 'other'),
hour=datetime.now().hour,
day_of_week=datetime.now().weekday()
)
sprout.close()
return jsonify({"status": "logged", "gentle": "thanks for telling me"})

@app.route('/api/productivity', methods=['POST'])
def log_productivity():
data = request.json
user_id = session.get('user_id', 1)
sprout = SproutRevealedPreference(user_id)
sprout.log_productivity(
energy_level=data['energy'],
tasks_completed=data.get('tasks', 0)
)
sprout.close()
return jsonify({"status": "ok", "message": "noted, no judgment"})

@app.route('/api/ask/<pattern_type>')
def ask_why(pattern_type):
user_id = session.get('user_id', 1)
sprout = SproutRevealedPreference(user_id)
insight = sprout.get_pattern_insight(pattern_type)
sprout.close()
if insight:
return jsonify({"insight": insight, "gentle": True})
return jsonify({"insight": "I haven't spotted that pattern yet. Keep being you — I'm watching gently."})

# ----- HTML/JS frontend (minimal but complete) -----
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
<title>Sprout · Revealed Preference Garden</title>
<style>
body { font-family: system-ui; background: #fdf8ed; padding: 2rem; text-align: center; }
.avatar-card { background: white; border-radius: 60px; padding: 2rem; max-width: 400px; margin: 0 auto; box-shadow: 0 8px 20px rgba(0,0,0,0.05); }
.avatar { font-size: 4rem; background: #eef3e0; border-radius: 100px; padding: 1rem; display: inline-block; margin: 1rem; }
button { background: #c7dfb5; border: none; padding: 10px 20px; border-radius: 40px; margin: 5px; cursor: pointer; }
.insight { background: #f0f4ea; border-radius: 28px; padding: 1rem; margin-top: 1rem; font-size: 0.9rem; }
select, input { padding: 8px; margin: 5px; border-radius: 30px; border: 1px solid #ddd; }
</style>
</head>
<body>
<div class="avatar-card">
<h2>🌱 Sprout's Garden</h2>
<div class="avatar" id="avatarDisplay">🦎</div>
<div>
<button onclick="changeAvatar('axolotl')">🦎 Axolotl</button>
<button onclick="changeAvatar('frog')">🐸 Frog</button>
<button onclick="changeAvatar('cat')">🐱 Cat</button>
<button onclick="changeAvatar('blob')">🫧 Blob</button>
</div>
<div style="margin: 1rem 0;">
<input type="number" id="spendAmount" placeholder="Amount spent">
<button onclick="logSpend()">log spend (no judgment)</button>
</div>
<div>
<select id="energyLevel">
<option value="1">Very low energy 😴</option>
<option value="3">Medium 😐</option>
<option value="5">High energy ⚡</option>
</select>
<button onclick="logProductivity()">log how I'm doing</button>
</div>
<div>
<button onclick="askWhy('friday_atm_habit')">🤔 Why the backpack?</button>
<button onclick="askWhy('low_energy_recovery_spending')">😴 Why sleepy eyes?</button>
<button onclick="askWhy('social_evening_spending')">🎉 Why party hat?</button>
</div>
<div id="insightBox" class="insight">✨ Your avatar changes based on gentle patterns I notice. Ask "why?" anytime.</div>
</div>
<script>
async function refreshAvatar() {
const res = await fetch('/api/avatar/state');
const data = await res.json();
document.getElementById('avatarDisplay').innerHTML = data.display;
}

async function changeAvatar(type) {
await fetch('/api/avatar/choose', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type}) });
refreshAvatar();
}

async function logSpend() {
const amount = parseFloat(document.getElementById('spendAmount').value);
if (amount) {
await fetch('/api/spend', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({amount, category: 'atm_withdrawal'}) });
document.getElementById('spendAmount').value = '';
refreshAvatar();
document.getElementById('insightBox').innerHTML = '🐟 logged. avatar might shift soon.';
}
}

async function logProductivity() {
const energy = document.getElementById('energyLevel').value;
await fetch('/api/productivity', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({energy, tasks: 1}) });
refreshAvatar();
document.getElementById('insightBox').innerHTML = '🌿 noted. I see you.';
}

async function askWhy(pattern) {
const res = await fetch(`/api/ask/${pattern}`);
const data = await res.json();
document.getElementById('insightBox').innerHTML = `🧠 ${data.insight}`;
}

refreshAvatar();
setInterval(refreshAvatar, 30000);
</script>
</body>
</html>
'''

if __name__ == '__main__':
app.run(debug=True, port=5001)
