from flask import Flask,render_template,request,redirect
import os
app = Flask(__name__)
app.config['SECRET_KEY']=os.urandom(32).hex()
@app.route('/')
def index():
    return render_template('index.html', 
                        title='Flask Template',
                        name='User',
                        messages=['Message 1', 'Message 2'])

@app.route('/login')
def login():
    if request.method == 'POST':
        if request.form.get('usrname') != 'admin':
            return "NO!"
        else:
            return 'Yes!'
    return 'SO!'
@app.route('/post/<int:post_id>')
def show_post(post_id):
    return f'Post {post_id}'

if __name__ == '__main__':
    app.run(debug= True)