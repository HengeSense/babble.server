import logging
import simplejson as json
from datetime import datetime
from datetime import timedelta
from pytz import utc

from zope.interface import implements

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from OFS.Folder import Folder

from Products.BTreeFolder2.BTreeFolder2 import manage_addBTreeFolder

from interfaces import IChatService
from conversation import Conversation
from chatroom import ChatRoom
from utils import hashed
import config

log = logging.getLogger(__name__)

class ChatService(Folder):
    """ """
    implements(IChatService)
    security = ClassSecurityInfo()
    security.declareObjectProtected('Use Chat Service')


    def _getUserAccessDict(self):
        if not hasattr(self, '_v_user_access_dict'):
            log.warn("_getUserAccessDict: Volatile User Access Dict was not found")
            setattr(self, '_v_user_access_dict', {})

        return getattr(self, '_v_user_access_dict')


    def _setUserAccessDict(self, username):
        """ """
        now = datetime.now()
        if hasattr(self, '_v_user_access_dict'):
            uad = getattr(self, '_v_user_access_dict')
            if uad.get(username, datetime.min) + timedelta(seconds=30) < now:
                uad[username] = now
        else:
            log.warn("_setUserAccessDict: Volatile User Access Dict was not found")
            setattr(self, '_v_user_access_dict', {username: now})


    def _getChatRoomsFolder(self):
        """ The 'ChatRooms' folder is a BTreeFolder that contains IChatRoom objects.
        """
        if not self.hasObject('chatrooms'):
            log.warn("The chatservice's 'ChatRooms' folder did not exist, "
                    "and has been automatically recreated.")
            manage_addBTreeFolder(self, 'chatrooms', 'ChatRooms')

        return self._getOb('chatrooms')


    def _getConversationsFolder(self):
        """ The 'Conversations' folder is a BTreeFolder that contains
            IConversation objects.

            See babble.server.interfaces.py:IConversation
        """
        if not self.hasObject('conversations'):
            log.warn("The chatservice's 'Conversations' folder did not exist, "
                    "and has been automatically recreated.")
            manage_addBTreeFolder(self, 'conversations', 'Conversations')

        return self._getOb('conversations')


    def _getConversation(self, user1, user2):
        """ """
        folder = self._getConversationsFolder()
        id = '.'.join(sorted([hashed(user1), hashed(user2)]))
        if not folder.hasObject(id):
            folder._setObject(id, Conversation(id, user1, user2))
        return folder._getOb(id)


    def _getConversationsFor(self, username):
        """ """
        f = self._getConversationsFolder()
        username = hashed(username)
        return [f._getOb(i) for i in f.objectIds() if username in i.split('.')]


    def _getChatRooms(self, ids):
        folder = self._getChatRoomsFolder()
        if type(ids) == str:
            ids= [ids]
        crs = []
        for c in ids:
            crs.append(folder._getOb(hashed(c)))
        return crs


    def _getChatRoom(self, id):
        folder = self._getChatRoomsFolder()
        return folder._getOb(hashed(id))


    def _getChatRoomsFor(self, username):
        folder = self._getChatRoomsFolder()
        rooms = []
        for chatroom in folder.values():
            if username in chatroom.participants:
                rooms.append(chatroom)
        return rooms


    def _authenticate(self, username, password):
        """ Authenticate the user with username and password """
        return self.acl_users.authenticate(username, password, self.REQUEST)


    def _isOnline(self, username, uad):
        """ Determine whether the user is (probably) currently online
        """
        last_confirmed_date = uad.get(username, datetime.min)
        cutoff_date = datetime.now() - timedelta(seconds=60)
        return last_confirmed_date > cutoff_date


    def _isRegistered(self, username):
        return self.acl_users.getUser(username) and True or False


    def createChatRoom(self, username, password, path, participants):
        if self._authenticate(username, password) is None:
            log.warn('createChatRoom: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        folder = self._getChatRoomsFolder()
        id = hashed(path)
        folder._setObject(id, ChatRoom(id, path, participants))
        return json.dumps({'status': config.SUCCESS})

    
    def addChatRoomParticipant(self, username, password, path, participant):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None or \
                not self._isRegistered(participant):

            log.warn('addChatRoomParticipant: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        try:
            chatroom = self._getChatRoom(path)
        except KeyError:
            return json.dumps({
                    'status': config.NOT_FOUND, 
                    'errmsg': "Chatroom '%s' doesn't exist" % id, 
                    })
        if participant not in chatroom.participants:
            chatroom._addParticipant(participant)
        return json.dumps({'status': config.SUCCESS})


    def editChatRoom(self, username, password, id, participants):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('getMessages: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})
        try:
            chatroom = self._getChatRoom(id)
        except KeyError:
            return json.dumps({
                    'status': config.NOT_FOUND, 
                    'errmsg': "Chatroom '%s' doesn't exist" % id, 
                    })

        chatroom.participants = participants
        chatroom.partner = {}
        for p in participants:
            chatroom.partner[p] = chatroom.client_path
        return json.dumps({'status': config.SUCCESS})


    def removeChatRoom(self, username, password, id):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('getMessages: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        parent = self._getChatRoomsFolder()
        hid = hashed(id)
        if hid not in parent.keys():
            return json.dumps({'status': config.NOT_FOUND})
        parent.manage_delObjects([hid])
        return json.dumps({'status': config.SUCCESS})


    def confirmAsOnline(self, username):
        """ See interfaces.IChatService """
        if username is None:
            return json.dumps({
                            'status': config.ERROR,
                            'errmsg': 'Username may not be None',
                            })

        self._setUserAccessDict(username)
        return json.dumps({'status': config.SUCCESS})


    def register(self, username, password):
        """ See interfaces.IChatService """
        user = self.acl_users.userFolderAddUser(
                                    username, 
                                    password, 
                                    roles=(), 
                                    domains=(), 
                                    last_msg_date=config.NULL_DATE )
        user.last_cleared_date = config.NULL_DATE
        return json.dumps({'status': config.SUCCESS})


    def isRegistered(self, username):
        """ See interfaces.IChatService """
        return json.dumps({
                    'status': config.SUCCESS, 
                    'is_registered': self._isRegistered(username)})


    def setUserPassword(self, username, password):
        """ See interfaces.IChatService """
        self.acl_users.userFolderEditUser(
                username, password, roles=(), domains=())
        return json.dumps({'status': config.SUCCESS})


    def getOnlineUsers(self):
        """ See interfaces.IChatService """
        uad = self._getUserAccessDict()
        ou = [user for user in uad.keys() if self._isOnline(user, uad)]
        return json.dumps({'status': config.SUCCESS, 'online_users': ou})


    def sendMessage(self, username, password, fullname, recipient, message):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('sendMessage: authentication failed')
            return json.dumps({
                    'status': config.AUTH_FAIL, 
                    'last_msg_date': config.NULL_DATE
                    })

        conversation = self._getConversation(username, recipient)
        last_msg_date = conversation.addMessage(message, username, fullname).time
        return json.dumps({
                'status': config.SUCCESS, 
                'last_msg_date': last_msg_date
                })


    def sendChatRoomMessage(self, username, password, fullname, room_name, message):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('sendChatRoomMessage: authentication failed')
            return json.dumps({
                    'status': config.AUTH_FAIL, 
                    'last_msg_date': config.NULL_DATE
                    })
        try:
            chatroom = self._getChatRoom(room_name)
        except KeyError:
            return json.dumps({
                    'status': config.ERROR, 
                    'errmsg': "Chatroom '%s' doesn't exist" % room_name, 
                    })

        last_msg_date = chatroom.addMessage(message, username, fullname).time
        return json.dumps({
                'status': config.SUCCESS, 
                'last_msg_date': last_msg_date
                })


    def _getMessagesFromContainers(self, containers, username, since, until):
        """ Generic conversation-type agnostic method that fetches messages.
        """
        last_msg_date = config.NULL_DATE
        msgs_dict = {}
        for container in containers:
            if not container.partner.has_key(username):
                log.warn(u"The container '%s' doesn't have '%s' as a partner. "
                         u"This shouldn't happen!" % (container.id, username))
                continue

            msg_tuples = []
            mbox_messages = []
            for mbox in container.values():
                for i in mbox.objectIds():
                    i = float(i)
                    mdate = datetime.utcfromtimestamp(i).replace(tzinfo=utc).isoformat()

                    if mdate > until:
                        continue

                    if mdate > last_msg_date:
                        # We want the latest date that's smaller than 'until'
                        last_msg_date = mdate

                    if mdate <= since:
                        continue

                    m = mbox._getOb('%f' % i)
                    msg_tuples.append((i, m))
            
            msg_tuples.sort()
            for i, m in msg_tuples:
                try:
                    mbox_messages.append((m.author, m.text, m.time, m.fullname))
                except AttributeError as e:
                    # BBB
                    if str(e) == 'fullname':
                        mbox_messages.append((m.author, m.text, m.time, m.author))
                    else:
                        raise AttributeError, e

            if mbox_messages:
                msgs_dict[container.partner[username]] = tuple(mbox_messages)

        return msgs_dict, last_msg_date


    def _getMessages(self, username, partner, chatrooms, since, until): 
        """ Returns messages within a certain date range

            This is an internal method that assumes authentication has 
            been done.
        """ 
        if since is None:
            since = config.NULL_DATE
        elif not config.VALID_DATE_REGEX.search(since):
            return {'status': config.ERROR, 
                    'errmsg': 'Invalid date format',}

        if until is None:
            until = datetime.now(utc).isoformat()
        elif not config.VALID_DATE_REGEX.search(until):
            return {'status': config.ERROR, 
                    'errmsg': 'Invalid date format',}

        if partner == '*':
            conversations = self._getConversationsFor(username)
        elif partner:
            conversations = [self._getConversation(username, partner)]
        else:
            conversations = []

        if chatrooms == '*':
            chatrooms = self._getChatRoomsFor(username)
        else:
            try:
                chatrooms = self._getChatRooms(chatrooms)
            except KeyError, e:
                return {'status': config.ERROR, 
                        'errmsg': "Chatroom %s doesn't exist" % e,}

        messages, last_msg_date = \
            self._getMessagesFromContainers(conversations, username, since, until)

        chatroom_msgs, last_chat_date = \
            self._getMessagesFromContainers(chatrooms, username, since, until)

        if last_chat_date > last_msg_date:
            last_msg_date = last_chat_date
                
        return {'status': config.SUCCESS, 
                'messages': messages,
                'chatroom_messages': chatroom_msgs,
                'last_msg_date':last_msg_date }


    def getMessages(self, username, password, partner, chatrooms, since, until):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('getMessages: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        return json.dumps(self._getMessages(
                                        username, 
                                        partner, 
                                        chatrooms, 
                                        since, until))


    def getNewMessages(self, username, password, since):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('getNewMessages: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        if since == config.NULL_DATE:
            user = self.acl_users.getUser(username)
            since = user.last_cleared_date

        user = self.acl_users.getUser(username)
        result = self._getMessages(username, '*', '*', since, None)
        return json.dumps(result)


    def getUnclearedMessages(self, username, password, partner, chatrooms, until, clear):
        """ See interfaces.IChatService """
        if self._authenticate(username, password) is None:
            log.warn('getUnclearedMessages: authentication failed')
            return json.dumps({'status': config.AUTH_FAIL})

        user = self.acl_users.getUser(username)
        if not hasattr(user, 'last_cleared_date'):
            user.last_cleared_date = config.NULL_DATE

        since = user.last_cleared_date
        result = self._getMessages(username, partner, chatrooms, since, until)
        if clear:
            user.last_cleared_date = result['last_msg_date']

        return json.dumps(result)


InitializeClass(ChatService)

