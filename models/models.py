#!/usr/bin/python
# -*- coding: utf-8 -*-

import time, random, string, pymongo
from bson import objectid
from bson.son import SON

import urllib, hashlib, zlib
import cPickle as pickle

my_secret = "***************"

# 暗号化のための関数
def encode_data(data):
  text = zlib.compress(pickle.dumps(data, 0)).encode("base64").replace("\n", "")
  m = hashlib.md5(my_secret+text).hexdigest()[:12]
  return m, text

# 復号化のための関数
def decode_data(hash, enc):
  text = urllib.unquote(enc)
  m = hashlib.md5(my_secret+text).hexdigest()[:12]
  if m != hash:
    raise Exception("Bad hash!")
  data = pickle.loads(zlib.decompress(text.decode("base64")))
  return data


class DatabaseConnection(object):
    __single = None

    def __init__(self, host="localhost", port=27017, dbname='gifpad'):
        self.db = pymongo.Connection(host=host, port=port)[dbname]
        return self

    def __new__(clz):
        if not DatabaseConnection.__single:
            DatabaseConnection.__single = DatabaseConnection.__init__(object.__new__(clz))
        return DatabaseConnection.__single.db


class User(object):
    table_name = "user"

    @staticmethod
    def save(userdoc):
        col = DatabaseConnection()[User.table_name]
        col.save(userdoc)
        return None

    @staticmethod
    def sign_up(**kwargs):
        col = DatabaseConnection()[User.table_name]
        judge = u"username" if col.find_one({'username':kwargs["username"]}) else u"email" if kwargs["email"] and col.find_one({'email':kwargs["email"]}) else None 
        if judge: return judge  # 既にユーザー名かEmailが登録済の場合, 該当の文字列が返る

        hash, enctext = encode_data(kwargs["password"])

        # keyとなるhash文字列暗号化した文字列と共にlist形式でinsert
        col.insert({'email': kwargs["email"], 'aboutuser': '', 'username': kwargs["username"], 'password': [hash,enctext], 'createdtime': time.time(), 'boardids':[]}, safe=True)
        return None

    @staticmethod
    def sign_in(username, password):
        col = DatabaseConnection()[User.table_name]
        if not col.find_one({'username': username}): return False
        passwordpair = col.find_one({'username': username})['password']
        stored_password = decode_data(*passwordpair)
        if stored_password == password: return True  # 入力されたパスワード文字列と復号化したパスワードが合致していた場合の分岐
        else: return False 

    @staticmethod
    def fetch_userboards(username):
        db = DatabaseConnection()
        coluser = db[User.table_name]
        colboard = db[Board.table_name]
        colimg = db[Img.table_name]
        item = coluser.find_one({"username":username})
        if len(item["boardids"]) == 0: return None 
        boarddocs_and_imgdocs = []
        for boardid in item["boardids"]:
          boarddoc = colboard.find_one({"_id":objectid.ObjectId(boardid)})
          imgdocs = colimg.find({"username": boarddoc["username"], "board": boarddoc["board"]})
          boarddocs_and_imgdocs.append((boarddoc, imgdocs))
        return reversed(boarddocs_and_imgdocs)

    @staticmethod
    def fetch_userdoc(username, keyforreset=None):
        col = DatabaseConnection()[User.table_name]
        if keyforreset:
          return col.find_one({"keyforreset":keyforreset})
        return col.find_one({"username":username})

    @staticmethod
    def fetch_boardids(username):
        col = DatabaseConnection()[User.table_name]
        return col.find_one({"username": username})["boardids"] 

    @staticmethod
    def fetch_boards(username, edit=None):
        col = DatabaseConnection()[User.table_name]
        boardids = col.find_one({"username": username})["boardids"] 
        if edit: return (Board().fetch_boardli_from_boardids(boardids), boardids)
        return Board().fetch_boardli_from_boardids(boardids)

    @staticmethod
    def update_email(**kwargs):
        col = DatabaseConnection()[User.table_name]

        if kwargs["email"]:
          existing_userdoc = col.find_one({"email": kwargs["email"]})
          if existing_userdoc:
            if kwargs["username"] != existing_userdoc["username"]: return "error"  # POSTされたユーザー名と元々格納していたemailのユーザー名が異なる場合の分岐

        col.update({"username": kwargs["username"]}, {"$set": {"email": kwargs["email"], "aboutuser": kwargs["aboutuser"]}})
        return None 

    @staticmethod
    def update_pw(newpassword, username=None, keyforreset=None):
        hash, enctext = encode_data(newpassword)
        if username:          # ログインでのパスワード変更
          col = DatabaseConnection()[User.table_name]
          col.update({'username': username}, {"$set" : {'password': [hash,enctext]}})  
          return None
        elif keyforreset:     # 未ログインでのパスワード変更
          db = DatabaseConnection()
          userdoc = db.command(SON({'findandmodify': 'user'},            # password fieldをアップデートし、keyforreset fieldを削除する
            query = {'keyforreset': keyforreset},
            update = {'$set': {'password': [hash,enctext]}, "$unset": {"keyforreset":keyforreset}}))["value"]
          return userdoc


    @staticmethod
    def add_keyforreset(username, keyforreset):
        col = DatabaseConnection()[User.table_name]
        userdoc = col.find_one({"username":username}) 
        userdoc["keyforreset"] = keyforreset
        User().save(userdoc) 

    @staticmethod
    def pop_boardid(username, boardid):
        col = DatabaseConnection()[User.table_name]
        userdoc = col.find_one({"username":username})  # 以下三行でユーザーコレクションで管理中のBoadidsフィールドから該当ボードIDを削除
        userdoc["boardids"].pop(userdoc['boardids'].index(unicode(boardid, "utf-8")))  # 文字列型をunicode型に変換
        User().save(userdoc)
        return None


class Img(object):
    table_name = "img"

    @staticmethod
    def add(**kwargs):
        col = DatabaseConnection()[Img.table_name]
        pagename = "".join([random.choice(string.ascii_letters+string.digits+'_') for i in range(38)])
        if "from_externalurl" in kwargs:  # ドキュメント追加(外部サイト経由時) 
          return str(col.insert({"username":kwargs["username"], "filename":kwargs["filename"], "from_externalurl":kwargs["from_externalurl"], "tags":kwargs["tags"],
                                 "description":kwargs["description"], "board":kwargs["board"], "pagename":pagename, "createdtime":time.time()}, safe=True))
 
        elif "fromimgid" not in kwargs:  # ドキュメント追加(Upload時)
          return str(col.insert({"username":kwargs["username"], "filename":kwargs["filename"], "tags":kwargs["tags"].split(), "description":kwargs["description"],
                                 "board":kwargs["board"], "pagename":pagename, "createdtime":time.time()}, safe=True))  # ボードドキュメントに登録させるためuniqueIDを返す
        else:  # ドキュメント追加(Regif時)
          return str(col.insert({"username":kwargs["username"], "filename":kwargs["filename"], "fromimgid":kwargs["fromimgid"], "tags":kwargs["tags"], "description":kwargs["description"],
                                 "board":kwargs["board"], "pagename":pagename, "createdtime":time.time()}, safe=True))  # 上に同じ

    @staticmethod
    def delete(pagename):
        col = DatabaseConnection()[Img.table_name]
        col.remove({"pagename":pagename})
        return None 

    @staticmethod
    def delete_multi(username, board):
        col = DatabaseConnection()[Img.table_name]
        col.remove({"username": username, "board": board}) 
        return None

    @staticmethod
    def change_board(**kwargs):
        col = DatabaseConnection()[Img.table_name]
        if "pagename" not in kwargs:  # 各ボード名編集時に伴い(複数の)Gifドキュメントのボード名フィールドの一括変更
          col.update({"username": kwargs["username"], "board": kwargs["oldboard"]}, {"$set": {"board": kwargs["newboard"]}}, multi=True)
          return None
        else:  # Gifが登録されているボード名フィールドの変更
          col.update({"pagename": kwargs["pagename"]}, {"$set": {"board": kwargs["newboard"], "tags": kwargs["tags"], "description": kwargs["description"]}})
          return None 

    @staticmethod
    def fetch_latest_imgdoc(username):
        col = DatabaseConnection()[Img.table_name]
        icondocs = [icondoc for icondoc in col.find({"username": username}).sort("_id", -1).limit(1)]
        if len(icondocs) == 0: icon_filename = "usericon.png"
        else: icon_filename = icondocs[0]["filename"]
        return icon_filename

    @staticmethod
    def fetch_imgdoc(pagename):
        col = DatabaseConnection()[Img.table_name]
        return col.find_one({"pagename":pagename}) 

    @staticmethod
    def fetch_imgdocs(username, board, per_page, page):
        db = DatabaseConnection()
        colimg = DatabaseConnection()[Img.table_name]
        return [doc for doc in colimg.find({"username": username, "board": board}).sort("_id", -1).limit(per_page).skip(per_page*(page-1))]

    @staticmethod
    def fetch_from_imgid(imgid, regif=None):
        col = DatabaseConnection()[Img.table_name]
        return col.find_one({"_id": objectid.ObjectId(imgid)}) if not regif else col.find({"fromimgid": imgid}).sort("_id", -1)
        # regifに文字列がassignされた場合、他にRegifして生成されたpageのdocsが返される

    @staticmethod
    def fetch_limitedimgdocs(per_page, page, tag=None):
        col = DatabaseConnection()[Img.table_name]
        dict = {} if not tag else {"tags": tag} 
        return col.find(dict).sort("_id", -1).limit(per_page).skip(per_page*(page-1))


class Readyimg(object):
    table_name = "readyimg"

    @staticmethod
    def add(username, filename):
        col = DatabaseConnection()[Readyimg.table_name]
        col.insert({"username": username, "filename": filename, "createdtime": time.time()}, safe=True)
        return None

    @staticmethod
    def fetch_readyimgdoc(imgid):
        col = DatabaseConnection()[Readyimg.table_name]
        return col.find_one({"_id":objectid.ObjectId(imgid)})

    @staticmethod
    def fetch_filename(dataid):
        col = DatabaseConnection()[Readyimg.table_name]
        return col.find_one({"_id":objectid.ObjectId(dataid)})["filename"]

    @staticmethod
    def fetch_imgid(filename):
        col = DatabaseConnection()[Readyimg.table_name]
        return str(col.find_one({"filename": filename})["_id"])

    @staticmethod
    def fetch_idlist(username):
        col = DatabaseConnection()[Readyimg.table_name]
        cur = col.find({"username": username})
        readyidlist = []
        for i in cur:
          readyidlist.append(str(i["_id"]))
        return readyidlist 

    @staticmethod
    def remove(dataid):
        col = DatabaseConnection()[Readyimg.table_name]
        col.remove({"_id":objectid.ObjectId(dataid)})
        return None


class Board(object):
    table_name = "board"
    @staticmethod
    def add(board, description, username):
        col = DatabaseConnection()[Board.table_name]
        return str(col.insert({"board": board, "description": description, "username": username, "createdtime": time.time()}))  # ユーザーコレクションのboardsフィールド用にobjectidを返す

    @staticmethod
    def delete(username, board):
        db = DatabaseConnection()
        colboard = DatabaseConnection()[Board.table_name]
        colimg = DatabaseConnection()[Img.table_name]
        removedid = str(colboard.find_one({"username": username, "board": board})["_id"])
        colboard.remove({"username":username, "board":board})  # 該当のボードドキュメントを削除
        colimg.remove({"username": username, "board": board})  # 該当の画像ドキュメントを削除
        return removedid 

    @staticmethod
    def change_board(**kwargs):
        col = DatabaseConnection()[Board.table_name]
        col.update({"username": kwargs["username"], "board": kwargs["oldboard"]}, {"$set": {"board": kwargs["newboard"], "description": kwargs["description"]}})
        return None 

    @staticmethod
    def fetch_description(username, board):
        col = DatabaseConnection()[Board.table_name]
        return col.find_one({"username": username, "board": board})["description"]

    @staticmethod
    def fetch_boarddoc(username, board):
        col = DatabaseConnection()[Board.table_name]
        return col.find_one({"username": username, "board": board})

    @staticmethod
    def fetch_boardli_from_boardids(boardids): 
        col = DatabaseConnection()[Board.table_name]
        boardsli = []
        for boardid in boardids:
          board = col.find_one({"_id":objectid.ObjectId(boardid)})["board"]
          boardsli.append(board)
        return boardsli


class Comment(object):
    table_name = "comment"

    @staticmethod
    def add(**kwargs):
        db = DatabaseConnection()
        col = db[Comment.table_name]

        result = db.command(SON({'findandmodify': 'next_public_id'},
          query = {"_id": "manager"},
          update = {"$inc":{"next_public_id": 1} },
          upsert = True
        ))
        manager = result["value"]
        id = manager.get("next_public_id", 0)

        col.insert({"id": id, "pagename": kwargs["pagename"], "username": kwargs["username"], "comment":kwargs["comment"], "createdtime": time.time()})
        return id 

    @staticmethod
    def delete(username, gifId, comId):
        col = DatabaseConnection()[Comment.table_name]
        if col.find_one({"username": username, "id":int(comId), "pagename": gifId}):
          col.remove({"id":int(comId), "pagename": gifId})
          return True
        else:
          return False

    @staticmethod
    def fetch_comments(pagename):
        col = DatabaseConnection()[Comment.table_name]
        return col.find({"pagename": pagename})
