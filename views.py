#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, string, random, datetime, time, json, urllib, urllib2, re, logging, itertools
from datetime import timedelta
from functools import wraps
from flask import (
     Flask, render_template, url_for, request, redirect, session, flash, abort, jsonify
     )
from jinja2 import utils
from flaskext.babel import Babel, gettext
import PIL.Image as Image

from forms import (
     Sign_upform, Sign_inform, Passwordform, ResetPwform, AddGifform, CreateGifform, UploadGifform,
     CreateBoardform, EditBoardform, EditGifform, Regifform, Settingform, ChangePwform
     )
from BeautifulSoup import BeautifulSoup
import models.models as models
import network.client as client

# 各種設定
PER_PAGE = 15

app = Flask(__name__)
UPLOAD_FOLDER = app.root_path+'/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = '***************'
app.permanent_session_lifetime = timedelta(hours=24)
app.config.from_pyfile('mysettings.cfg')


# テンプレートの国際化
babel = Babel(app)

@babel.localeselector
def getlocate():
    return request.accept_languages.best_match(['ja', 'ja_JP', 'en'])


# CSRF対策
def generate_csrf_token():
    if '_csrf_token' not in session:
      session['_csrf_token'] = "".join([random.choice(string.ascii_letters+string.digits+'_') for i in range(30)])
    return session['_csrf_token']  

@app.before_request
def csrf_protect():
    if request.method == "POST" and request.is_xhr is False:
      token = session.pop('_csrf_token', None)
      if not token or token != request.form.get('_csrf_token'):
        abort(403)

app.jinja_env.globals['csrf_token'] = generate_csrf_token


# 独自filter登録
def mklag(s):
    result = (int(time.time()) - int(s)) / 60
    if result == 0: timelag = gettext(u"a minute ago")
    elif 0 < result < 60: timelag = str(result) + gettext(u" minutes ago")
    elif 60 <= result < 1440: timelag = str(result/60) + gettext(u" hours ago") if str(result/60) != "1" else gettext(u"a hour ago")
    elif 1440 <= result < 10080: timelag = str(result/1440) + gettext(u" days ago") if str(result/1440) != "1" else gettext(u"a day ago")
    elif 10080 <= result < 40320: timelag = str(result/10080) + gettext(u" weeks ago") if str(result/10080) != "1" else gettext(u"a week ago")
    elif 40320 <= result < 483840: timelag = str(result/40320) + gettext(u" months ago") if str(result/40320) != "1" else gettext(u"a month ago")
    else: timelag = gettext(u"Over a year ago")
    return timelag 

def uriencode(gifurl):
    return urllib.quote_plus(gifurl) 

app.jinja_env.filters['mklag'] = mklag
app.jinja_env.filters['uriencode'] = uriencode


if not app.debug:
    from logging import FileHandler
    file_handler = FileHandler(os.path.join(app.root_path+"/logs/gifpad.log"))
    file_handler.setLevel(logging.INFO)    
    app.logger.addHandler(file_handler)


# 複数のフレームで構成されているか否かで、アニメGifかどうかの判定を行います。加えて、画像のサイズが大きい場合リサイズとファイルサイズの判定も行います
class Agifjudge(object):
    def __init__(self, path, page=None):
      self.path = path
      self.page = page
 
    def validate(self):
      im = Image.open(self.path)
      try:
        im.seek(1)
      except EOFError:  # isanimated False
        os.remove(self.path)
        return 'upload/receiver' if self.page == 'upload/receiver' else 'gif/create'
      else:             # isanimated True
        # GIF animation resize 
        (width, height) = (im.size[0], im.size[1])
        if width > 500 or height > 400:
          os.system('sudo convert %s -coalesce -resize 400x400 -deconstruct %s' % (self.path, self.path))
        # ファイルサイズ判定
        if os.path.getsize(self.path) > 5242880:  # ファイルサイズが5Mbyte以上の場合error分岐させる
          return 'upload/receiver' if self.page == 'upload/receiver' else 'gif/create'


# 多重ループから抜け出すためのclass
class END(Exception):
    pass


# Views
@app.route("/submit", methods=["GET"])
def submit():
    if 'username' in session: return redirect(url_for("index"))
    form1 = Sign_upform(request.form)
    form2 = Sign_inform(request.form)
    return render_template("anonymous/submit.html", form1=form1, form2=form2, submit="submit")


@app.route("/password", methods=["GET", "POST"])
def send_email():
    if 'username' in session: return redirect(url_for("index"))
    if request.method == "GET":
      form = Passwordform(request.form)
      form1 = Sign_upform(request.form)
      form2 = Sign_inform(request.form)
      return render_template("anonymous/send_email.html", form=form, form1=form1, form2=form2)

    form = Passwordform()
    form.username.data = request.form["data"] 
    if request.method == "POST" and request.is_xhr is True and form.validate():
      userdoc = models.User().fetch_userdoc(form.username.data)
      if not userdoc or not userdoc["email"]:    # 未登録のユーザとemailが未登録のユーザーはエラー分岐
        return jsonify(res="error", message=gettext("this user don't use email"))

      # 外部のメールサーバーとソケット通信します
      keyforreset = client.connectExtServer(userdoc["username"], userdoc["email"])
      models.User().add_keyforreset(userdoc["username"], keyforreset)
      return jsonify(res="success", message=gettext("an email will be sent to that account's address shortly"))
    else: 
      return jsonify(res="error", message=gettext("this user don't use email"))


@app.route("/resetpassword/<keyforreset>", methods=["GET"])
def reset_password(keyforreset):
    if 'username' in session: return redirect(url_for("index"))
    if models.User().fetch_userdoc(None, keyforreset):
      form = ResetPwform(request.form)
      form1 = Sign_upform(request.form)
      form2 = Sign_inform(request.form)
      return render_template("anonymous/resetpassword.html", form=form, form1=form1, form2=form2)
    else: return redirect(url_for("send_email"))


@app.route("/resetpassword/receiver", methods=["POST"])
def receive_resetpassword():
    if request.is_xhr is True:
      data = request.form["data"]
      keyforreset = request.args.get("keyforreset")
      form = ResetPwform()
      dict = {}
      for i in data.split("&"):
        dict[i.split("=")[0]] = i.split("=")[1]
      (form.newpassword.data, form.verifypassword.data) = (dict["newpassword"], dict["verifypassword"])
      if form.validate():
        userdoc = models.User().update_pw(form.newpassword.data, None, keyforreset)  # 変更したユーザードキュメントを代入
        session["username"] = userdoc["username"] 
        return jsonify(res="success")
      else:
        for field_name, field_errors in form.errors.items():
          for error in field_errors:
            return jsonify(res="error", message=error)


@app.route("/user/sign_up", methods=["POST"])
def sign_up():
    if request.is_xhr == True:
      form1 = Sign_upform()
      data = request.form["data"]
      dict = {}
      for i in data.split("&"):
        dict[i.split("=")[0]] = i.split("=")[1]
      (form1.username.data, form1.password.data) = (dict["username"], dict["password"]) 
      if dict["email"]: # 以下4行Emailの@のreplace
        r = re.compile("(%40)")
        form1.email.data = r.sub("@", dict["email"])
      else: form1.email.data = ""

      if form1.validate():
        judge = models.User().sign_up(email=form1.email.data, username=form1.username.data, password=form1.password.data)
        if not judge:
          judge = form1.validate_banned_username()

        if not judge: # 登録成功の分岐
          session["username"] = form1.username.data
          return jsonify(res="success") 
        else:
          message = gettext(u"This username is used") if judge == "username" else gettext(u"This email is used")
          return jsonify(res=message, op="sign_up")
      else:
        for field_name, field_errors in form1.errors.items():
          for error in field_errors:
            return jsonify(res=error, op="sign_up")

    form1 = Sign_upform(request.form)
    if request.is_xhr == False and form1.validate():
      judge = models.User().sign_up(email=form1.email.data, username=form1.username.data, password=form1.password.data)
      if not judge:
        judge = form1.validate_banned_username()

      if not judge: # 登録成功の分岐
        session["username"] = form1.username.data
        return redirect(url_for("index"))
      else:
        message = gettext(u"This username is used") if judge == "username" else gettext(u"This email is used")
        flash(message, 'sign_up')
        return redirect(url_for("submit"))
    else:           
      for field_name, field_errors in form1.errors.items():
        for error in field_errors:
          flash(error, 'sign_up')
      return redirect(url_for("submit"))


@app.route("/user/sign_in", methods=["POST"])
def sign_in():
    if request.is_xhr is True:
      form2 = Sign_inform()
      data = request.form["data"]
      dict = {}
      for i in data.split("&"):
        dict[i.split("=")[0]] = i.split("=")[1]

      (form2.username.data, form2.password.data) = (dict["username"], dict["password"])
      if form2.validate():
        if models.User().sign_in(dict["username"], dict["password"]):
          session["username"] = dict["username"] 
          return jsonify(res="success")
        else:
          return jsonify(res=gettext("Wrong username or password"), op="sign_in")
      else:
        for field_name, field_errors in form2.errors.items():
          for error in field_errors:
            return jsonify(res=error, op="sign_in") 

    form2 = Sign_inform(request.form)
    if request.is_xhr is False and form2.validate():
      if models.User().sign_in(form2.username.data, form2.password.data):
        session["username"] = form2.username.data
        return redirect(url_for("index"))
      else:
        flash(gettext(u"Wrong username or password"), "sign_in") 
        return redirect(url_for("submit"))
    else:
      for field_name, field_errors in form2.errors.items():
        for error in field_errors:
          flash(error, "sign_in")
      return redirect(url_for("submit"))


# ここからサインインが必要なViewが混在します
def sign_in_required(f):
    @wraps(f)
    def wrapper(*args, **kw):
      if not 'username' in session: return redirect(url_for("submit"))
      return f(*args, **kw)
    return wrapper


@app.route("/user/sign_out", methods=["GET"])
@sign_in_required
def sign_out():
    session.pop('username', None)
    return redirect(url_for("index"))


@app.route("/user/setting", methods=["GET", "POST"])
@sign_in_required
def setting():
    form = Settingform(request.form)
    userdoc = models.User().fetch_userdoc(session["username"]) 
    if request.method == "GET":
      (form.email.data, form.aboutuser.data) = (userdoc["email"], userdoc["aboutuser"])
      return render_template("setting.html", form=form, sign_in_username=session['username'])

    if request.method == "POST" and form.validate():

      # サインインしているユーザー以外のメルアドが入力されたらエラー分岐されます
      if models.User().update_email(username=session["username"], email=form.email.data, aboutuser=form.aboutuser.data): 
        return render_template("setting.html", form=form, sign_in_username=session['username'],
                               update_email_error=gettext(u"This email belongs to another user"))
      return redirect(url_for("userboards", username=session["username"]))
    else: 
      return render_template("setting.html", form=form, sign_in_username=session['username'])


@app.route("/user/password", methods=["GET", "POST"])
@sign_in_required
def change_password():
    form = ChangePwform(request.form)
    userdoc = models.User().fetch_userdoc({"username":session["username"]}) 
    if request.method == "GET":
      return render_template("change_password.html", form=form, sign_in_username=session["username"]) 

    if request.method == "POST" and form.validate():
      if not models.User().sign_in(session["username"], form.currentpw.data):
        return render_template("change_password.html", form=form, sign_in_username=session["username"],
                               current_pw_error=gettext(u"Your current password was incorrectly. Please enter it again."))
      models.User().update_pw(form.newpw.data, session["username"])
      return redirect(url_for("userboards", username=session['username']))
    else:
      return render_template("change_password.html", form=form, sign_in_username=session["username"]) 


@app.route("/", defaults={'page': 1}, methods=["GET"])
@app.route("/page/<page>", methods=["GET"])
def index(page):
    form2 = Sign_inform(request.form)
    imgdocs = models.Img().fetch_limitedimgdocs(**{"per_page":PER_PAGE, "page": int(page)})  
    if "username" not in session:
      if int(page) >= 6: return abort(404)
      return render_template("anonymous/index.html", items=imgdocs, form1=Sign_upform(request.form), form2=Sign_inform(request.form)) # 非登録ユーザーには別テンプレートでレンダリング

    return render_template("index.html", items=imgdocs, sign_in_username=session["username"]) 


@app.route("/tag/<tag>", defaults={'page': 1}, methods=["GET"])
@app.route("/tag/<tag>/<page>", methods=["GET"])
def tag(tag, page):
    imgdocs = models.Img().fetch_limitedimgdocs(**{"per_page":PER_PAGE, "page": int(page), "tag": tag})
    if "username" not in session:
      return render_template("anonymous/tag.html", items=imgdocs, next=tag, form1=Sign_upform(request.form), form2=Sign_inform(request.form))

    return render_template("tag.html", items=imgdocs, next=tag, sign_in_username=session['username'])


@app.route("/<username>", methods=["GET"])
def userboards(username):
    userdoc = models.User().fetch_userdoc(username)
    if not userdoc: return abort(404) # ユーザー名が登録されていない場合404へ

    userboards = models.User().fetch_userboards(username)
    if userboards:
      (userboards, cp) = itertools.tee(userboards) # ユーザーボードのイテレータobjectのコピーを生成するため分割させる
      username = list(cp)[0][0]["username"]  
    else:
      userboards = [] 

    if "username" not in session:
      return render_template("anonymous/userboards.html", userboards=userboards, useritem=userdoc, form1=Sign_upform(request.form), form2=Sign_inform(request.form))

    return render_template("userboards.html", userboards=userboards, sign_in_username=session["username"], useritem=userdoc)


@app.route("/<username>/<board>", defaults={'page':1}, methods=["GET"])
@app.route("/<username>/<board>/<page>", methods=["GET"])
def userboard(username, board, page):
    imgdocs = models.Img().fetch_imgdocs(username, board, PER_PAGE, int(page))
    if int(page) >= 2 and len(imgdocs) == 0: return abort(404)

    description = models.Board().fetch_description(username, board)

    if "username" not in session:
      return render_template("anonymous/userboard.html", items=imgdocs, username=username, board=board,
                                                         description=description, form1=Sign_upform(request.form), form2=Sign_inform(request.form))
    return render_template("userboard.html", items=imgdocs, sign_in_username=session['username'],
                           username=username, board=board, description=description)


@app.route("/<username>/<board>/edit", methods=["GET", "POST"])
@sign_in_required
def edit_userboard(username, board):
    boarddoc = models.Board().fetch_boarddoc(username, board)
    form = EditBoardform(request.form)
    if boarddoc['username'] != session['username']: return abort(404) # ボードの管理ページに非管理者ユーザーが接続してきた場合404へ

    if request.method == "GET":
      return render_template("edit_userboard.html", form=form, boarddoc=boarddoc, sign_in_username=session["username"],
                             placeho_board=boarddoc['board'], placeho_description=boarddoc['description'])

    if request.method == "POST" and form.validate():
      (existing_boards, existing_ids) = models.User().fetch_boards(username, edit="edit")

      for (existing_board, existing_id) in zip(existing_boards, existing_ids):  # 既に存在しているボード名の場合の条件分岐
        if existing_board == form.board.data and existing_id != str(boarddoc["_id"]):
          return render_template("edit_userboard.html", form=form, boarddoc=boarddoc, placeho_board=boarddoc['board'], sign_in_username=session["username"],
                                 placeho_description=boarddoc['description'], edit_board_error=gettext(u"This boardname is created"))

      models.Board().change_board(username=username, oldboard=board, newboard=form.board.data, description=form.description.data)  # Board Collectionの該当docをUpdate
      models.Img().change_board(username=username, oldboard=board, newboard=form.board.data)  # Img Collectionの該当docsをUpdate
      return redirect(url_for("userboard", username=username, board=form.board.data))
    else:   
      return render_template("edit_userboard.html", form=form, boarddoc=boarddoc, sign_in_username=session["username"],
                             placeho_board=boarddoc['board'], placeho_description=boarddoc['description'])


@app.route("/<username>/<board>/delete", methods=["GET"])
@sign_in_required
def delete_userboard(username, board):
    if username != session["username"]: return abort(404) 
    removedid = models.Board().delete(session["username"], board)  # BoardとImg docsが削除され、BoardのIDが返る。...ファイル削除しない方向で...
    models.User().pop_boardid(session["username"], removedid)
    models.Img().delete_multi(session["username"], board)
    return redirect(url_for("userboards", username=session["username"]))


@app.route("/gif/<pagename>", methods=["GET"])
def gifpage(pagename):
    imgdoc = models.Img().fetch_imgdoc(pagename)
    if imgdoc == None: return abort(404)  # 存在しないGifの個別ページに接続してきた場合404へ

    fromimgdoc = models.Img().fetch_from_imgid(imgdoc["fromimgid"]) if "fromimgid" in imgdoc else None  # Noneがassignされる時はNot Regifなページ

    regifedimgdocs = models.Img.fetch_from_imgid(imgdoc["fromimgid"], regif="regif") if "fromimgid" in imgdoc else \
                     models.Img.fetch_from_imgid(str(imgdoc["_id"]), regif="regif")  # オリジナルのGifであることが確定すると、Regifされ生成されたdocsを返す(else以下)

    if regifedimgdocs:
      (regifedimgdocs, cp) = itertools.tee(regifedimgdocs)  # (オリジナルを)Regifしてできたimgdocsのイテレータobjectのコピーを生成するため分割させる
      regifs = len((list(cp)))
    else: regifs = None 

    commentdocs = models.Comment.fetch_comments(pagename)

    if "username" not in session:
      return render_template("anonymous/gif.html", item=imgdoc, fromitem=fromimgdoc,  regifeditems=regifedimgdocs, regifs=regifs,
                                                   form1=Sign_upform(request.form), form2=Sign_inform(request.form), icon_filename="usericon.png",
                                                   commentitems=commentdocs)
                            
    icon_filename = models.Img.fetch_latest_imgdoc(session["username"])
    return render_template("gif.html", item=imgdoc, fromitem=fromimgdoc, regifeditems=regifedimgdocs, regifs=regifs, icon_filename=icon_filename,
                                       commentitems=commentdocs, sign_in_username=session["username"])


@app.route("/gif/<pagename>/edit", methods=["GET", "POST"])
@sign_in_required
def edit_gifpage(pagename):
    imgdoc = models.Img().fetch_imgdoc(pagename)
    if imgdoc["username"] != session["username"]: return abort(404)  # Gifの編集ページに非管理者ユーザーが接続してきた場合404へ

    form = EditGifform(request.form) 
    boards_li = models.User().fetch_boards(session["username"])
    form.board.choices = [(index, board) for (index, board) in zip(range(1, len(boards_li)+1), boards_li)]  # 動的にoption要素の値を出力するための下処理

    if request.method == "GET":
      form.description.data = imgdoc["description"]
      return render_template("edit_gif.html", form=form, item=imgdoc, sign_in_username=session["username"])

    if request.method == "POST" and form.validate() and form.validate_tags(request.form.getlist("item[tags][]")):
      tags = request.form.getlist("item[tags][]")

      index = request.form["board"]
      newboard = boards_li[int(index)-1]
      description = request.form["description"]
      models.Img().change_board(pagename=pagename, newboard=newboard, tags=tags, description=description)  # 単一Gifのボード名変更 
      return redirect(url_for("gifpage", pagename=pagename))
    else:
      return render_template("edit_gif.html", form=form, item=imgdoc, sign_in_username=session["username"])


@app.route("/gif/<pagename>/delete", methods=["GET"])
@sign_in_required
def delete_gifpage(pagename):
    username = models.Img().fetch_imgdoc(pagename)["username"]
    if username != session["username"]: return abort(404) 
    models.Img().delete(pagename)  # Img Collectionの該当のGifdocを削除します
    # Gifのファイル自体は削除しない方向です
    return redirect(url_for("userboards", username=session["username"]))


@app.route("/gif/<pagename>/regif", methods=["GET", "POST"])
@sign_in_required
def regif(pagename):
    imgdoc = models.Img().fetch_imgdoc(pagename)
    if imgdoc["username"] == session["username"]: return abort(404) # GifのRegifページに管理者ユーザーが接続してきた場合404へ

    form = Regifform(request.form)
    boards_li = models.User().fetch_boards(session["username"])
    form.board.choices = [(index, board) for (index, board) in zip(range(1, len(boards_li)+1), boards_li)]  # 動的にoption要素の値を出力するための下処理

    if request.method == "GET":
      return render_template("regif.html", form=form, item=imgdoc, sign_in_username=session["username"])

    if request.method == "POST" and form.validate() and form.validate_tags(request.form.getlist("item[tags][]")):
      index = request.form["board"]
      tags = request.form.getlist("item[tags][]")
      description = request.form["description"]
      regifed_board = boards_li[int(index)-1]
      fromimgid = str(imgdoc["fromimgid"]) if "fromimgid" in imgdoc else str(imgdoc["_id"])

      imgid = models.Img().add(username=session["username"], filename=imgdoc["filename"], description=description, tags=tags,
                              fromimgid=fromimgid, board=regifed_board)

      return redirect(url_for("userboard", username=session["username"], board=regifed_board))
    else:
      return render_template("regif.html", form=form, item=imgdoc, sign_in_username=session["username"])


@app.route("/gif/<pagename>/comment", methods=["POST"])
@sign_in_required
def comment(pagename):
    if request.is_xhr is True:
      if not 0 < len(request.form["data"]) <= 500:
        return jsonify(res="error")

      comment = str(utils.escape(request.form["data"]))  # for xss filtering
      icon = str(utils.escape(request.form["icon"]))  # for xss filtering
      id = models.Comment().add(pagename=pagename, username=session["username"], comment=comment)  # コメントのIDを返す。このIDはMongoDBの備え付けのIDではない

      data = "<div class='comment' data-id='%s'><div class='pic'><img src='%s' style='width:45px;height:45px;' alt=''></div><div class='content'>\
              <div class='flright'><a href='#' data-gifId='%s' data-comId='%s'>x</a></div>\
              <a href='/%s'>%s</a><br>%s<p style='clear:both;float:none;'></p></div></div>"  % (id, icon, pagename, id, session["username"], session["username"], comment)
 
      return jsonify(res=data)


@app.route("/comment/delete/<gifId>", methods=["POST"])
@sign_in_required
def delete_comment(gifId):
    if request.method == "POST" and request.is_xhr is True:
      comId = request.form["data"]
      if models.Comment().delete(session["username"], gifId, comId):
        return jsonify(res="success")
      else:  # コメントしたユーザー以外の削除要求が来た場合の分岐
        return jsonify(res="failure") 


@app.route("/gif/add", methods=["GET"])
@sign_in_required
def add_gif():
    form = AddGifform()
    if not request.args.get("source_url"):
      return render_template("addgif.html", form=form, sign_in_username=session['username'])
    else:  # formからのGET通信要求の場合の分岐
      form.source_url.data = request.args.get("source_url")
      if form.validate():
        src = urllib2.urlopen(form.source_url.data).read()
        soup = BeautifulSoup(src)
        source_gifurls = [imgsrc["src"] for imgsrc in soup.findAll("img", src=re.compile("^(http://).*(\.gif)$"))]  # imgタグを元にsrcプロパティ(GIF限定)のリストをつくる

        return render_template("addgif.html", form=form, sign_in_username=session['username'], source_url_encoded=urllib.quote_plus(form.source_url.data), source_gifurls=source_gifurls)
      else:
        return render_template("addgif.html", form=form, sign_in_username=session['username'])


@app.route("/gif/create", methods=["GET", "POST"])
@sign_in_required
def create_gif():
    form = CreateGifform(request.form) 
    boards_li = models.User().fetch_boards(session["username"])
    form.board.choices = [(index, board) for (index, board) in zip(range(1, len(boards_li)+1), boards_li)]  # 動的にoption要素の値を出力するための下処理
    source_url_encoded = urllib.quote_plus(request.args.get("source_url")) # querystrigをURIエンコード

    if request.method == 'GET':
      return render_template("creategif.html", form=form, sign_in_username=session['username'], source_url_encoded=source_url_encoded, source_gifurl=request.args.get("source_gifurl"))

    if request.method == 'POST' and form.validate() and form.validate_tags(request.form.getlist("item[tags][]")):
      filename = "".join([random.choice(string.ascii_letters+string.digits+'_') for i in range(21)])+".gif"
      dir = os.path.join(app.config['UPLOAD_FOLDER'], filename)
      urllib.urlretrieve(request.args.get("source_gifurl"), dir)
      agifjudge = Agifjudge(dir)

      if agifjudge.validate() == 'gif/create':  # アニメイトしていないor5M以上のGifの場合の分岐
        return render_template("creategif.html", form=form, sign_in_username=session['username'], source_url_encoded=source_url_encoded,
                                                 source_gifurl=request.args.get("source_gifurl"), gif_error=True)

      board = boards_li[int(request.form["board"])-1]
      models.Img().add(username=session["username"], filename=filename, description=form.description.data, tags=request.form.getlist("item[tags][]"),
                      board=board, from_externalurl=request.args.get("source_gifurl"))
      return redirect(url_for("index"))

    else:
      return render_template("creategif.html", form=form, sign_in_username=session['username'], source_url_encoded=source_url_encoded, source_gifurl=request.args.get("source_gifurl"))


@app.route("/gif/up", methods=["GET", "POST"])
@sign_in_required
def upload_gif():
    boards_li = models.User().fetch_boards(session["username"])
    form = UploadGifform(request.form) 
    form.board.choices = [(index, board) for (index, board) in zip(range(1, len(boards_li)+1), boards_li)]  # 動的にoption要素の値を出力するための下処理

    if request.method == 'GET':
      return render_template("uploadgif.html", form=form, sign_in_username=session['username'])

    if request.method == 'POST' and form.validate():
      texts = request.form["hidden"]
      index = request.form["board"] 
      board = boards_li[int(index)-1]

      dict = json.loads(texts) 
      Postedidlist = []
      (li, imgli) = (dict.keys(), [])
      for (k, i) in zip(li, range(len(li))):
        if k.startswith("description") and len(k) == 37:
          descriptionid = k.lstrip("description[").rstrip("]")
          for (comparedelemen, comparedi) in zip(li, range(len(li))):
            if comparedelemen.startswith("tags") and len(comparedelemen) == 30:
              tagsid = comparedelemen.lstrip("tags[").rstrip("]")
              if descriptionid == tagsid:
                Postedidlist.append(descriptionid)

      readyidlist = models.Readyimg().fetch_idlist(session["username"]) 

      list = []
      for element in Postedidlist:
        index = readyidlist.index(element)
        tuple = (index, element)
        list.append(tuple)
        list.sort()

      try:  # このtry, except文は実質的なvalidationにあたる
        for sortedid in list:
          if not 0 <= len(dict["description["+sortedid[1]+"]"]) <= 200:
            return render_template("uploadgif.html", form=form, sign_in_username=session['username'])
          if not 1 <= len(dict["tags["+sortedid[1]+"]"].split()) <= 5:
            return render_template("uploadgif.html", form=form, sign_in_username=session['username'])
          for tag in dict["tags["+sortedid[1]+"]"].split():
            if not 1 <= len(tag) <= 20: raise END 
            if not re.compile(u"^([a-zA-Z0-9_-]|[ぁ-ん０-９＿ー]|[ァ-ヴ]|[一-龠])+$").search(tag): raise END 
      except END:  # 不正なタグが入力された時error分岐
        return render_template("uploadgif.html", form=form, sign_in_username=session['username'])

      for sortedid in list:
        readyimgdoc = models.Readyimg().fetch_readyimgdoc(sortedid[1])
        models.Img().add(username=readyimgdoc["username"], filename=readyimgdoc["filename"], description=dict["description["+sortedid[1]+"]"],
                                tags=dict["tags["+sortedid[1]+"]"], board=board)

      return redirect(url_for("userboard", username=session["username"], board=board)) 
    else:
      return render_template("uploadgif.html", form=form, sign_in_username=session['username'])


@app.route("/upload/receiver", methods=["POST"])
@sign_in_required
def receive_uploaded_file():
    if request.is_xhr is True and request.method == "POST":
      if request.headers['Content-Type'] == 'application/octet-stream':
        filename = "".join([random.choice(string.ascii_letters+string.digits+'_') for i in range(21)])+".gif"
        dir = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f = open(dir, 'wb')
        f.write(request.data)
        f.close()
        agifjudge = Agifjudge(dir, 'upload/receiver')
        if agifjudge.validate() == 'upload/receiver': return ""  # アニメイトしていないGifの場合の分岐

        models.Readyimg().add(session["username"], filename)
        boards = models.User().fetch_boards(session["username"])
        imgid = models.Readyimg().fetch_imgid(filename)

        return jsonify(success="success", username=session['username'], fname=filename, boards=boards, dataid=imgid) 


@app.route("/gif_delete/receiver/<dataid>", methods=['DELETE'])
@sign_in_required
def gif_delete_receiver(dataid):
    if request.is_xhr is True and 'username' in session:
      readyimgdoc = models.Readyimg().fetch_readyimgdoc(dataid) 
      if readyimgdoc["username"] != session["username"]: return jsonify(error=u"error") 
      models.Readyimg().remove(dataid)
      os.remove(os.path.join(app.config['UPLOAD_FOLDER'], readyimgdoc['filename']))
      return jsonify(dataid=dataid) 


@app.route("/board/create", methods=["GET", "POST"])
@sign_in_required
def create_board():
    form = CreateBoardform(request.form)
    if request.method == "GET":
      return render_template("createboard.html", form=form, sign_in_username=session["username"])

    if request.method == "POST" and form.validate():
      userdoc = models.User().fetch_userdoc(session["username"]) 
      boardli = models.Board().fetch_boardli_from_boardids(userdoc["boardids"])  # UserCollectionで管理中のBoardのIDにリストを引数にBoardのリストをBoardCollから(ry

      for board in boardli:  # 既に同一ネームのボードが存在した時、templateにエラー出力
        if board == form.board.data:
          return render_template("createboard.html", form=form, create_board_error=gettext(u"This boardname is created"), sign_in_username=session["username"])
      boardid = models.Board().add(form.board.data, form.description.data, session["username"])

      userdoc['boardids'].append(boardid)  # 新規登録されたボードのIDをUser Collectionでボードfieldに追加
      models.User().save(userdoc)
      return redirect(url_for("userboards", username=session["username"]))
    else:
      return render_template("createboard.html", form=form, sign_in_username=session["username"])


# Web serverで静的ファイルを配信する場合は下から11行コメントアウトしてください
from flask import send_from_directory
STATIC_FOLDER = './static/'
app.config['STATIC_FOLDER'] = STATIC_FOLDER 


@app.route("/uploads/<filename>")
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route("/static/<format>/<filename>")
def static_file(format, filename): return send_from_directory(app.config['STATIC_FOLDER'], format+'/'+filename)


@app.errorhandler(500)
def page_not_found(e): return render_template('404.html'), 404

@app.errorhandler(404)
def page_not_found(e): return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
