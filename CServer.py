from socket import *
import threading
import struct
from enum import Enum
import time
from CDataBase import *

class EnumMessageType(Enum):
    ANONYMOUS=1
    CHAT=2
    ONE2ONE=3
    REGISTER=4
    LOGIN=5
    ADDFRIEND=6
    SEARCHUSER=7
    FILETRANS=8
    MSGRECORD=9
    UPDATEUSER=10

class CServerSocket():
    #看看是不是这里
    conn=CSqlForChat()
    def __init__(self,ip,port):
        ADDR=(ip,port)
        #初始化socket
        print('正在启动服务器....')
        self.socketServer=socket(AF_INET,SOCK_STREAM)
        self.socketServer.bind(ADDR)
        self.socketServer.listen()
        print("服务器启动成功,等待客户端连接....")
        #外部调用的accept接口
    def MyAccept(self):
        #创建线程accept
        t=threading.Thread(target=self.__acceptProc__)
        t.start()
    def __acceptProc__(self):
        while True:
            #_accept返回的是个元组（套接字，客户端地址）
            socketClient,addrClient=self.socketServer.accept()
            #socketClient.send("连接成功！".encode('gb2312'))
            CServerSocket.dictClient[socketClient]=None
            #创建单独线程等待客户端消息
            #创建线程接收消息
            t=threading.Thread(target=self.__recvProc__,args=(socketClient,))
            t.start()
    #接收消息的线程
    def __recvProc__(self,s):
        while True:
            try:
                message=s.recv(CServerSocket.BUFSIZE+10)
                #消息类型
                type,=struct.unpack("i",message[:4])
                CServerSocket.dictFun[type](s,message)
            except Exception as TheExp:
                print(str(TheExp))
                name=CServerSocket.dictClient.get(s)
                if name==None:
                    return
                s.close()
                name=CServerSocket.dictClient.pop(s)
                print("客户端退出："+name)
                CServerSocket.UpdateUser(s,False,name)
                return
            #不同聊天目的的回调函数，即用于匿名，也用于登录聊天
    def __ChatForAnonymous__(s,msg):
        dwLen,=struct.unpack("L",msg[4:8])
        buf,=struct.unpack("%ds" % dwLen,msg[8:8+dwLen])
        name=buf.decode("gb2312")
        print(name+"加入聊天室")
        CServerSocket.dictClient[s]=name.rstrip('\0')
        for each in CServerSocket.dictClient:
            each.send(msg)
        CServerSocket.UpdateUser(s,True,name)
        #通知给每个客户端跟新在线用户列表
        #########################################

    #添加到在线用户队列里
    def UpdateUser(s,bAdd,name):
        try:
            message_type=EnumMessageType.UPDATEUSER
            message=name.encode('gb2312')
            message_len=len(message)
            message_send=struct.pack("lll2040s",message_type.value,bAdd,message_len,message)
            for each in CServerSocket.dictClient:
                if each==s:
                    continue
                each.send(message_send)
            if bAdd==False:
                return
                #再给新用户的在线列表添加之前登录的用户名
            for each in CServerSocket.dictClient:
                if each==s:
                    continue
                message=CServerSocket.dictClient[each].encode("gb2312")
                message_len=len(message)
                message_send=struct.pack("lll2040s",message_type.value,bAdd,message_len,message)
                s.send(message_send)
        except:
            return

                #
            #先给所有客户端的用户列表里添加新用户
    #匿名聊天
    def __ChatForChat__(s,msg):
        dwLen,=struct.unpack("L",msg[4:8])
        buf,=struct.unpack("%ds"%dwLen,msg[8:8+dwLen])
        #解密
        buf=bytearray(buf)
        for i in range(dwLen):
            buf[i]^=15
        message_recv=buf.decode("gb2312")
        print(message_recv)
        for each in CServerSocket.dictClient:
            if each ==s:
                continue
            each.send(msg)
    #1v1聊天 服务器要把A发来的消息 B:你好 转换成 A:你好
    def __ChatForFiletrans__(s, msg):
        name, = struct.unpack("50s", msg[4:54])
        name = name.decode("gb2312").rstrip('\0')
        for each in CServerSocket.dictClient:
            if name == CServerSocket.dictClient[each]:
                name = struct.pack("50s", CServerSocket.dictClient[s].encode("gb2312"))
                each.send(msg[:4] + name + msg[54:])
                break
    def __ChatForOne2One__(s,msg):
        name,=struct.unpack("50s",msg[4:54])
        name=name.decode("gb2312").rstrip('\0')
        for each in CServerSocket.dictClient:
            if name==CServerSocket.dictClient[each]:
                name=struct.pack("50s",CServerSocket.dictClient[s].encode('gb2312'))
                each.send(msg[:4]+name+msg[54:])
                break
        #是否保存聊天记录
        #消息双方姓名
        msgFrom=CServerSocket.dictClient[s]
        msgTo,=struct.unpack("50s",msg[4:54])
        msgTo=msgTo.decode("gb2312").rstrip('\0');
        #消息内容
        msginfo,=struct.unpack("1024s",msg[54:54+1024])
        msginfo=msginfo.decode("gb2312").rstrip('\0');
        #把消息添加到数据库，数据库设置外键了，只会添加双方都是注册用户的聊天信息
        CServerSocket.conn.insert("insert into msginfo(userfrom,userto,msgcontent)VALUES (%s,%s,%s)",(msgFrom,msgTo,msginfo))
    def __ChatForLogin__(s,msg):

        name, = struct.unpack("50s", msg[4:54])
        pwd, = struct.unpack("50s", msg[54:104])
        name = name.decode("gb2312").rstrip('\0')
        pwd = pwd.decode("gb2312").rstrip('\0')
        result = CServerSocket.conn.query("SELECT * from userinfo WHERE name=%s and pwd=%s", (name, pwd))
        # 返回登录结果
        # 登录失败
        message_type = EnumMessageType.LOGIN
        message_len = 50
        message = ""
        if result == None or result[1]==0:
         message = "登录失败!".encode("gb2312")
        else:
            message = "登录成功!".encode("gb2312")
        message_send = struct.pack("l2048s", message_type.value, message)
        s.send(message_send)
    def __ChatForRegister__(s,msg):
        try:
             name, = struct.unpack("50s", msg[4:54])
             pwd,=struct.unpack("50s", msg[54:104])
             name=name.decode("gb2312").rstrip('\0')
             pwd=pwd.decode("gb2312").rstrip('\0')
             #构造查询语句

             result=CServerSocket.conn.insert("INSERT into userinfo (name,pwd) VALUES(%s,%s)",(name,pwd))
             #返回登录结果
             #登录失败
             message_type=EnumMessageType.REGISTER
             message_len=50
             message=""
             if result==None:
                 message="注册失败!".encode("gb2312")
             else:
                 message="注册成功!".encode("gb2312")
             message_send=struct.pack("l2048s",4,message)
             s.send(message_send)
        except Exception as TheExp:
             print(str(TheExp))
    def __ChatForAddFriend__(s,msg):
        name, = struct.unpack("50s", msg[4:54])
        frd, = struct.unpack("50s", msg[54:104])
        name = name.decode("gb2312").rstrip('\0')
        frd = frd.decode("gb2312").rstrip('\0')
        result=CServerSocket.conn.insert("INSERT into userfriend (name,friend) VALUES(%s,%s)",(name,frd))
        message_type=EnumMessageType.ADDFRIEND
        message_len=50
        message=""
        if result ==None:
            message="添加好友失败！".encode('gb2312')
        else:
            message = "添加好友成功！".encode('gb2312')
        message_send = struct.pack("l2048s", message_type.value, message)
        s.send(message_send)
    def __ChatForSearUser__(s,msg):
        name, = struct.unpack("50s", msg[4:54])
        name = name.decode("gb2312").rstrip('\0')
        result = CServerSocket.conn.query("SELECT name from userinfo WHERE name=%s", (name,))
        # 返回登录结果
        message_type = EnumMessageType.SEARCHUSER
        message_len = 50
        message = ""
        if result==None or result[1]==0:
            message="查无此人!".encode('gb2312')
        else:
            if name in CServerSocket.dictClient.values():
                message="用户在线，双击进行1v1聊天！".encode('gb2312')
            else:
                message="用户不在线！".encode('gb2312')
        message_send = struct.pack("l2048s", message_type.value, message)
        s.send(message_send)
    def __ChatForGetMsgRecord__(s,msg):
        name=CServerSocket.dictClient[s]
        #查询所以信息
        result=CServerSocket.conn.query("select * from msginfo where userfrom=%s or userto=%s",(name,name))
        if result==None or result[1]==0:
            return
        message_type=EnumMessageType.MSGRECORD
        for i in range(result[1]):
            #第一条信息
            print(str(i)+":")
            print("from:"+result[0][i][0].decode('utf-8'))
            print("to:"+result[0][i][1].decode('utf-8'))
            print("content:"+result[0][i][2].decode('utf-8'))

            msgFrom = result[0][i][0].decode('utf-8')
            msgTo = result[0][i][1].decode('utf-8')
            msgContent = result[0][i][2].decode('utf-8')

            msgFrom=msgFrom.encode("gb2312")
            msgTo = msgTo.encode("gb2312")
            msgContent = msgContent.encode("gb2312")
            # msgFrom=result[0][i][0].decode("gb2312")
            # msgTo=result[0][i][1].decode("gb2312")
            # msgContent=result[0][i][2].decode("gb2312")
            msgSend=struct.pack("l50s50s1948s",message_type.value,msgFrom,msgTo,msgContent)
            s.send(msgSend)
        #最后发个END过去，告诉客户端聊天记录全部发完
        msgFrom="~~~end~~~".encode("gb2312")
        msgSend=struct.pack("l2048s",message_type.value,msgFrom)
        s.send(msgSend)
    #类变量
    dictFun={
        1: __ChatForAnonymous__,
        2: __ChatForChat__,
        3: __ChatForOne2One__,
        4: __ChatForRegister__,
        5: __ChatForLogin__,
        6: __ChatForAddFriend__,
        7: __ChatForSearUser__,
        8: __ChatForFiletrans__,
        9: __ChatForGetMsgRecord__
    }
    BUFSIZE=2048+4
    dictClient={
    }


