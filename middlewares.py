import logging
from typing import Dict, Any, Callable, Awaitable

from aiogram import types, Dispatcher, BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import ALLOWED_USER_IDS

# Dictionary to track which users were already warned in which chats
warned_users: Dict[int, set] = {}


class AccessControlMiddleware(BaseMiddleware):
    """Middleware to control access to the bot's functionality."""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Check if the user has access rights."""
        user_id = event.from_user.id
        
        if isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
            message_obj = event.message
        else:
            chat_id = event.chat.id
            message_obj = event
        
        # Check if it's a private chat - ENABLED, bot works only in group chats
        if chat_id > 0:  # Private chat (chat_id is positive)
            if chat_id not in warned_users.get(user_id, set()):
                # Initialize set for user if not exists
                if user_id not in warned_users:
                    warned_users[user_id] = set()
                
                # Add chat to warned chats for user
                warned_users[user_id].add(chat_id)
                
                await message_obj.answer("🚫 Бот работает только в групповых чатах. Добавьте меня в группу обменника.")
            return None
        
        # Check if the user is allowed to use the bot
        if ALLOWED_USER_IDS != ["*"] and user_id not in ALLOWED_USER_IDS:
            logging.warning(f"Unauthorized access attempt: User ID {user_id} in chat {chat_id}")
            await message_obj.answer("🚫 Ошибка: У вас нет доступа к боту. Обратитесь к администратору.")
            return None
        
        # Store chat title for reference
        data['chat_title'] = message_obj.chat.title
        logging.info(f"Access granted to user {user_id} in group '{message_obj.chat.title}' (ID: {chat_id})")
        
        # Continue processing
        return await handler(event, data)


class GroupChatMiddleware(BaseMiddleware):
    """Middleware to ensure the bot only works in group chats (now disabled for testing)."""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Ensure the event came from a group chat (disabled for testing)."""
        if isinstance(event, CallbackQuery):
            chat = event.message.chat
            user_id = event.from_user.id
        else:
            chat = event.chat
            user_id = event.from_user.id
        
        # For testing, allow all chat types
        # Store chat title for reference (or 'Private Chat' for private chats)
        if chat.type in ('group', 'supergroup'):
            data['chat_title'] = chat.title
        else:
            data['chat_title'] = 'Private Chat'
            
        logging.info(f"Access granted to user {user_id} in chat type {chat.type} (ID: {chat.id})")
            
        # Continue processing
        return await handler(event, data)


def register_middlewares(dp: Dispatcher):
    """Register all middlewares."""
    dp.message.middleware(AccessControlMiddleware())
    dp.callback_query.middleware(AccessControlMiddleware())
    dp.message.middleware(GroupChatMiddleware())
    dp.callback_query.middleware(GroupChatMiddleware())
