#!/usr/bin/python
# -*- coding: utf-8 -*-

#############################
# このScriptはcliant側になります。
# TCP通信でEmailとユーザー名をserver側に送り、見返りに
# パスワードリセット入力のためのURLを貰います。
############################

from socket import *
import pickle

# 以下サーバー側のアドレス(ホスト, ポート)設定
HOST = 'xxx.xxx.xxx.xxx'
PORT = 20556
BUFSIZ = 1024
ADDR = (HOST, PORT)


def connectExtServer(username, email):
  tcpCliSock = socket(AF_INET, SOCK_STREAM)
  tcpCliSock.connect(ADDR)

  binary_data = pickle.dumps((username, email))

  while True:
    tcpCliSock.send(binary_data)
    keyforreset = tcpCliSock.recv(BUFSIZ)
    if keyforreset:
      break

  tcpCliSock.close()
  return keyforreset 
