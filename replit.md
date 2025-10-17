# Overview

This is a Telegram bot built with the aiogram 3.x framework (asynchronous Telegram Bot API library). The bot implements a verification system that requires users to join both a Telegram channel and WhatsApp channel before accessing features. It includes a referral tracking system and admin functionality for managing daily codes and user verification.

## Recent Changes (October 2025)
- Migrated from aiogram 2.x to 3.x with all breaking changes resolved
- Fixed channel verification system to properly extract channel username from URLs
- Fixed referral link system using CommandStart filter for deep link parameter handling
- Added environment variable validation with clear error messages on startup
- Fixed admin code update functionality to use global variable correctly
- All critical bugs resolved and bot is fully functional

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Technology**: aiogram (async Telegram Bot API wrapper for Python)
- **Rationale**: Modern, asynchronous Python framework that provides clean abstractions for handling Telegram bot interactions
- **Key Components**:
  - Router-based message handling for organized command/callback processing
  - Inline keyboard markup for interactive user flows
  - Command filters for structured command handling

## Application Flow
- **Verification System**: Two-step verification requiring users to join external channels (Telegram + WhatsApp) before accessing bot features
- **Referral Tracking**: Users can share referral links; the system tracks which users were referred by whom
- **State Management**: In-memory storage using Python sets and dictionaries for:
  - Verified users tracking (`verified_users`)
  - Referral relationships (`referrals`)
  - General user data (`user_data`)

## Authentication & Authorization
- **Admin System**: Single admin identified by ADMIN_ID environment variable
- **User Verification**: Channel membership verification before granting access
- **Daily Code System**: Configurable daily code stored in environment variables (purpose unclear from incomplete code)

## Configuration Management
- **Approach**: Environment variables loaded via python-dotenv
- **Required Variables**:
  - BOT_TOKEN: Telegram bot authentication token
  - CHANNEL_USERNAME: Telegram channel for verification
  - WHATSAPP_LINK: WhatsApp channel/group link
  - ADMIN_ID: Telegram user ID for admin access
  - DAILY_CODE: Optional daily verification/access code
- **Validation**: Strict startup validation ensures all critical variables are present

## Data Architecture
- **Storage**: In-memory Python data structures (no persistence)
- **Limitation**: All user data, referrals, and verification status are lost on bot restart
- **Trade-offs**:
  - Pros: Simple, no database setup required, fast access
  - Cons: No data persistence, not scalable for large user bases

# External Dependencies

## Telegram Bot API
- **Service**: Telegram's Bot API
- **Purpose**: Core bot functionality, message handling, user interaction
- **Integration**: Via aiogram library (BOT_TOKEN authentication)

## Telegram Channel
- **Service**: Telegram public/private channel
- **Purpose**: Verification requirement - users must join before accessing bot
- **Configuration**: CHANNEL_USERNAME environment variable

## WhatsApp Channel/Group
- **Service**: WhatsApp external channel or group
- **Purpose**: Secondary verification requirement
- **Integration**: Direct link shared with users (WHATSAPP_LINK)

## Python Libraries
- **aiogram**: Async Telegram bot framework
- **python-dotenv**: Environment variable management
- **asyncio**: Asynchronous runtime (Python standard library)

## Notes
- Code appears incomplete (truncated start_cmd function, empty main.py)
- No database integration currently - potential future addition for data persistence
- Bot uses webhook or polling mechanism (not visible in provided code)