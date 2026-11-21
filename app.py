#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import requests
from datetime import datetime, timedelta, timezone
from seleniumbase import SB
from selenium.common.exceptions import ElementClickInterceptedException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from zoneinfo import ZoneInfo

# ----- 配置（从环境变量读取或在双引号内填写） -----
EMAIL = os.getenv('EMAIL') or ""         # 邮箱必填
PASSWORD = os.getenv('PASSWORD') or ""   # 密码必填
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""  # CHAT_ID 可选
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or "" # BOT_TOKEN 可选，需同时填写CHAT_ID生效

LOGIN_PATH = '/auth/login'
LOGIN_URL = f'https://aclclouds.com{LOGIN_PATH}'
BASE_URL = 'https://aclclouds.com'
PROJECTS_URL = f'{BASE_URL}/dashboard/projects'
DASHBOARD_URL = f'{BASE_URL}/dashboard'

def beijing_time_str():
    try:
        return datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')

def send_telegram(message):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {'chat_id': TG_CHAT_ID, 'text': message}
        try:
            requests.post(url, data=data, timeout=10)
            print(f"Telegram sent: {message[:50]}...")
        except Exception as e:
            print(f"Failed to send Telegram: {e}")
    else:
        print(f"[Telegram disabled] {message}")

def parse_time_str(time_str):
    """解析提取到的时间字符串，返回 datetime 对象"""
    if not time_str or time_str in ['未知', '']:
        return None
    now = datetime.now()
    
    # 尝试提取纯相对时间: e.g., "3 days 4 hours"
    match_rel = re.search(r'(?:(\d+)\s*(?:days|day|天))?\s*(?:(\d+)\s*(?:hours|hour|小时))?', time_str, re.I)
    if match_rel and (match_rel.group(1) or match_rel.group(2)) and not re.search(r'\d{4}', time_str):
        days = int(match_rel.group(1) or 0)
        hours = int(match_rel.group(2) or 0)
        return now + timedelta(days=days, hours=hours)
    
    # 尝试匹配绝对时间 (YYYY-MM-DD)
    match_ymd = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?', time_str)
    if match_ymd:
        try:
            year, month, day = int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3))
            hour = int(match_ymd.group(4) or 0)
            minute = int(match_ymd.group(5) or 0)
            second = int(match_ymd.group(6) or 0)
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
            
    # 尝试匹配绝对时间 (DD/MM/YYYY 法国/欧洲格式)
    match_dmy = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?', time_str)
    if match_dmy:
        try:
            day, month, year = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
            hour = int(match_dmy.group(4) or 0)
            minute = int(match_dmy.group(5) or 0)
            second = int(match_dmy.group(6) or 0)
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
            
    return None

def format_remaining_time(expiry_str):
    """格式化剩余时间，返回如 ' (剩 120天4小时)'"""
    if not expiry_str or expiry_str == '未知':
        return ''
    dt = parse_time_str(expiry_str)
    if not dt:
        return ''
    
    now = datetime.now()
    delta = dt - now
    if delta.total_seconds() <= 0:
        return ' (已过期)'
    
    days = delta.days
    hours = delta.seconds // 3600
    if days > 0:
        return f" (剩 {days}天{hours}小时)"
    elif hours > 0:
        return f" (剩 {hours}小时)"
    else:
        minutes = (delta.seconds % 3600) // 60
        return f" (剩 {minutes}分钟)"

def wait_for_url_change(sb, original_url, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_url = sb.get_current_url()
        if current_url != original_url:
            return True
        sb.sleep(0.5)
    raise Exception(f"等待 URL 变化超时 ({timeout}秒)，当前仍为: {original_url}")

def is_login_page(sb):
    return LOGIN_PATH in sb.get_current_url()

def is_logged_in(sb):
    current_url = sb.get_current_url()
    return BASE_URL in current_url and LOGIN_PATH not in current_url

def scroll_to_selector(sb, selector):
    sb.scroll_to(selector)
    sb.sleep(0.2)

def safe_click_element(sb, element, label):
    try:
        sb.driver.execute_script(
            'arguments[0].scrollIntoView({block: "center", inline: "center"});',
            element,
        )
        sb.sleep(0.5)

        try:
            element.click()
            return True
        except (ElementClickInterceptedException, WebDriverException, StaleElementReferenceException) as e:
            print(f"{label} 普通点击失败，改用 JavaScript 点击: {e}")

        sb.driver.execute_script('arguments[0].click();', element)
        sb.sleep(0.5)
        return True
    except StaleElementReferenceException:
        print(f"{label} 元素已失效，点击前需要重新定位")
        return False

def element_text(element):
    try:
        return element.text.strip()
    except Exception:
        return ''

def unique_elements(elements):
    unique = []
    seen = set()
    for element in elements:
        element_id = getattr(element, 'id', None)
        if element_id and element_id in seen:
            continue
        if element_id:
            seen.add(element_id)
        unique.append(element)
    return unique

def element_contains(parent, child):
    if parent == child:
        return True
    try:
        return parent.find_elements(By.XPATH, './/*').count(child) > 0
    except Exception:
        return False

def dedupe_project_cards(cards):
    cards = unique_elements(cards)
    if not cards:
        return []

    keep = []
    for card in cards:
        card_text = element_text(card)
        if len(card_text) < 3:
            continue

        duplicate = False
        for kept in list(keep):
            kept_text = element_text(kept)
            if element_contains(kept, card):
                duplicate = True
                break
            if element_contains(card, kept):
                if len(card_text) > len(kept_text):
                    keep.remove(kept)
                else:
                    duplicate = True
                break

        if not duplicate:
            keep.append(card)

    deduped = []
    seen_signatures = set()
    for card in keep:
        text = element_text(card)
        name = ''
        for line in text.splitlines():
            line = line.strip()
            if line and not re.search(r'expires|renewal|renew|reactivate|suspended|expiry|expire|valid|续期|重新激活|恢复|暂停|过期|到期', line, re.I):
                name = line
                break
        signature = (name.lower(), get_project_expiry(card).lower())
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(card)

    return deduped

def find_elements(root, selector):
    by = By.XPATH if selector.startswith(('/', './/')) else By.CSS_SELECTOR
    return root.find_elements(by, selector)

def find_renew_buttons(root):
    selectors = [
        '.projects-renew-btn',
        './/button['
        'contains(translate(@title, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "renew") or '
        'contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "renew")]',
        './/button['
        'contains(translate(@title, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "reactivate") or '
        'contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "reactivate")]',
        './/button[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "renew")]',
        './/button[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "reactivate")]',
        './/*[(@role="button" or self::a) and contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "renew")]',
        './/*[(@role="button" or self::a) and contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "reactivate")]',
    ]
    buttons = []
    for selector in selectors:
        try:
            buttons.extend(find_elements(root, selector))
        except Exception:
            continue
    return unique_elements([button for button in buttons if element_text(button) or button.is_displayed()])

def find_card_container_from_child(sb, child):
    return sb.driver.execute_script(
        '''
        const start = arguments[0];
        let node = start;
        for (let i = 0; node && i < 10; i += 1, node = node.parentElement) {
          const text = (node.innerText || '').trim();
          const cls = (node.className || '').toString().toLowerCase();
          const looksLikeProject = /renew|reactivate|suspended|expiry|expire|expires|valid|续期|重新激活|恢复|暂停|过期|到期/i.test(text);
          const looksLikeCard = /card|project|service|server|item|row/.test(cls);
          if (node !== start && text.length > 20 && (looksLikeProject || looksLikeCard)) {
            return node;
          }
        }
        return start.parentElement || start;
        ''',
        child,
    )

def find_project_cards(sb):
    candidate_selectors = [
        '.projects-card',
        '[class*="projects-card"]',
        '[class*="project"][class*="card"]',
        '[class*="Project"][class*="Card"]',
        '[class*="service"][class*="card"]',
        '[class*="server"][class*="card"]',
        'article',
    ]
    cards = []
    for selector in candidate_selectors:
        try:
            for card in sb.driver.find_elements(By.CSS_SELECTOR, selector):
                text = element_text(card).lower()
                if any(keyword in text for keyword in ['renew', 'reactivate', 'suspended', 'expiry', 'expire', 'valid', 'manage', '续期', '重新激活', '恢复', '暂停', '过期', '到期']):
                    cards.append(card)
        except Exception:
            continue

    if cards:
        return dedupe_project_cards(cards)

    for button in find_renew_buttons(sb.driver):
        try:
            cards.append(find_card_container_from_child(sb, button))
        except Exception:
            continue

    if cards:
        return dedupe_project_cards(cards)

    expiry_xpath = (
        '//*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "expiry") '
        'or contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "expire") '
        'or contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "valid") '
        'or contains(normalize-space(.), "过期") or contains(normalize-space(.), "到期")]'
    )
    for elem in sb.driver.find_elements(By.XPATH, expiry_xpath):
        try:
            cards.append(find_card_container_from_child(sb, elem))
        except Exception:
            continue

    return dedupe_project_cards(cards)

def extract_date_like(text):
    if not text:
        return ''
    patterns = [
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?',
        r'\d{1,2}[-/]\d{1,2}[-/]\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ''

def extract_duration_like(text):
    if not text:
        return ''

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if re.search(r'expires\s+in|剩余|还有', line, re.I) and idx + 1 < len(lines):
            candidate = lines[idx + 1]
            if extract_date_like(candidate) or re.search(r'\d', candidate):
                return re.sub(r'^(?:expires\s*in|剩余|还有)\s*[:：]?\s*', '', candidate, flags=re.I).strip()

    match = re.search(
        r'(?:expires\s*in\s*)?(\d+\s*(?:days|day|d|j|天|日)\s*\d*\s*(?:hours|hour|h|小时)?)',
        text,
        re.I,
    )
    if match:
        return match.group(1).strip()

    match = re.search(r'\d+\s*(?:hours|hour|h|小时)', text, re.I)
    if match:
        return match.group(0).strip()

    return ''

def get_project_name(card, idx):
    selectors = [
        '.projects-card-title',
        'h1',
        'h2',
        'h3',
        'h4',
        '[class*="title"]',
        '[class*="name"]',
    ]
    for selector in selectors:
        try:
            for elem in card.find_elements(By.CSS_SELECTOR, selector):
                text = element_text(elem)
                if text and len(text) <= 80 and 'renew' not in text.lower() and 'expiry' not in text.lower() and not extract_duration_like(text):
                    return text
        except Exception:
            continue

    for line in element_text(card).splitlines():
        line = line.strip()
        if line and len(line) <= 80 and not extract_duration_like(line) and not re.search(r'renew|reactivate|suspended|expiry|expire|valid|续期|重新激活|恢复|暂停|过期|到期', line, re.I):
            return line
    return f"项目 #{idx}"

def get_project_expiry(card):
    selectors = [
        '.projects-expiry-value',
        '.projects-service-cell--expiry strong',
        '[class*="expiry"] strong',
        '[class*="expiry"] [class*="value"]',
        '[class*="expiry"]',
        '[class*="expire"]',
        '[class*="Expires"]',
        './/*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "expiry")]',
        './/*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "expire")]',
        './/*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "valid")]',
        './/*[contains(normalize-space(.), "过期") or contains(normalize-space(.), "到期")]',
    ]
    for selector in selectors:
        try:
            for elem in find_elements(card, selector):
                text = element_text(elem)
                date_text = extract_date_like(text)
                if date_text:
                    return date_text
                duration_text = extract_duration_like(text)
                if duration_text:
                    return duration_text
                if text and len(text) <= 120:
                    return text
        except Exception:
            continue

    card_text = element_text(card)
    return extract_date_like(card_text) or extract_duration_like(card_text) or '未知'

def get_renewal_available_note(card):
    text = element_text(card)
    patterns = [
        r'Renewal\s+will\s+be\s+available[^\n]*',
        r'可续期[^\n]*',
        r'续期[^\n]*前[^\n]*',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0).strip()
    return ''

def get_card_by_index(sb, idx):
    cards = find_project_cards(sb)
    if idx <= len(cards):
        return cards[idx - 1]
    return None

def wait_for_renew_result(sb, idx, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            success_modals = sb.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "modal") and contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "successfully")]',
            )
            if any(modal.is_displayed() for modal in success_modals):
                card = get_card_by_index(sb, idx)
                return True, get_project_expiry(card) if card else '未知', 'success modal'

            card = get_card_by_index(sb, idx)
            if card:
                renewal_note = get_renewal_available_note(card)
                renew_buttons = find_renew_buttons(card)
                if renewal_note and not renew_buttons:
                    return True, get_project_expiry(card), renewal_note
        except Exception as e:
            print(f"检查续期结果时暂时失败: {e}")

        sb.sleep(1)

    card = get_card_by_index(sb, idx)
    note = get_renewal_available_note(card) if card else ''
    expiry = get_project_expiry(card) if card else '未知'
    return False, expiry, note

def log_projects_page_diagnostics(sb):
    current_url = sb.get_current_url()
    title = sb.get_title()
    body_text = ''
    try:
        body_text = sb.driver.find_element(By.TAG_NAME, 'body').text.strip()
    except Exception:
        pass
    print(f"项目页诊断 URL: {current_url}")
    print(f"项目页诊断标题: {title}")
    print(f"项目页可见文本摘要: {body_text[:1200]}")

def has_renew_antibot_modal(sb):
    selectors = [
        '//div[contains(., "Anti-bot confirmation")]',
        '//div[contains(., "Confirm you are human")]',
        '//div[contains(., "I am not a robot")]',
    ]
    for selector in selectors:
        try:
            if any(elem.is_displayed() for elem in sb.driver.find_elements(By.XPATH, selector)):
                return True
        except Exception:
            continue
    return False

def get_cap_widget_state(sb):
    return sb.driver.execute_script(
        '''
        const hosts = document.querySelectorAll('cap-widget');
        for (const host of hosts) {
          if (!host.shadowRoot) continue;
          const box = host.shadowRoot.querySelector('.captcha');
          if (box) return box.getAttribute('data-state') || 'initial';
        }
        return 'missing';
        '''
    )

def find_cap_trigger(sb):
    return sb.driver.execute_script(
        '''
        const hosts = document.querySelectorAll('cap-widget');
        for (const host of hosts) {
          if (!host.shadowRoot) continue;
          const trigger = host.shadowRoot.querySelector('.captcha-trigger');
          if (trigger) return trigger;
        }
        return null;
        '''
    )

def click_captcha_checkbox(sb, label='验证码', timeout=10):
    max_attempts = 3
    state = ''
    for attempt in range(1, max_attempts + 1):
        try:
            sb.wait_for_element_visible('cap-widget', timeout=timeout)
        except Exception as e:
            print(f"{label} 未找到 Cap 验证组件: {e}")
            return False

        if attempt > 1:
            print(f"{label} 第 {attempt} 次尝试...")

        trigger = find_cap_trigger(sb)
        if trigger is None:
            print(f"{label} 未找到验证复选框")
            return False

        try:
            sb.driver.execute_script(
                'arguments[0].scrollIntoView({block: "center", inline: "center"});',
                trigger,
            )
        except Exception:
            pass

        state = get_cap_widget_state(sb)
        if state != 'verifying':
            try:
                trigger.click()
                print(f"{label} 已点击 Verify you're human 复选框")
            except (ElementClickInterceptedException, WebDriverException, StaleElementReferenceException) as e:
                print(f"{label} 普通点击失败，改用 JavaScript 点击: {e}")
                try:
                    sb.driver.execute_script('arguments[0].click();', trigger)
                except Exception as e2:
                    print(f"{label} JavaScript 点击也失败: {e2}")
                    return False

        sb.sleep(5)

        start_time = time.time()
        while time.time() - start_time < 30:
            state = get_cap_widget_state(sb)
            if state == 'done':
                print(f"{label} 验证通过（绿色对勾已出现）")
                return True
            if state == 'error':
                print(f"{label} 本次校验未通过（error 状态），准备重试")
                break
            sb.sleep(1)

    print(f"{label} 验证未通过，最后状态: {state}")
    return False

def mask_email(email):
    if not email or '@' not in email:
        return email or ''

    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '****' if local else '****'
    elif len(local) <= 4:
        masked_local = f"{local[0]}****{local[-1]}"
    else:
        masked_local = f"{local[:2]}****{local[-2:]}"
    return f"{masked_local}@{domain}"

def build_success_message(project_name, old_expiry, new_expiry):
    masked_email = mask_email(EMAIL)
    old_remaining = format_remaining_time(old_expiry)
    new_remaining = format_remaining_time(new_expiry)
    
    lines = [
        "🇫🇷 Aclclouds 续期通知",
        "",
        "✅ 续期成功",
        f"⏱️ 续期前: {old_expiry}{old_remaining}",
        f"⏱️ 续期后: {new_expiry}{new_remaining}",
        f"👤 登录账户: {masked_email}",
        f"⏱️ 运行时间: {beijing_time_str()}",
    ]
    return "\n".join(lines)

def build_not_yet_due_message(project_name, expiry):
    masked_email = mask_email(EMAIL)
    remaining = format_remaining_time(expiry)
    lines = [
        "🇫🇷 Aclclouds 续期通知",
        "",
        "⏳ 未到续期时间",
        f"⏱️ 当前过期: {expiry}{remaining}",
        f"👤 登录账户: {masked_email}",
        f"⏱️ 运行时间: {beijing_time_str()}",
    ]
    return "\n".join(lines)

def build_unconfirmed_message(project_name, old_expiry, new_expiry, result_note):
    masked_email = mask_email(EMAIL)
    old_remaining = format_remaining_time(old_expiry)
    new_remaining = format_remaining_time(new_expiry)
    
    lines = [
        "🇫🇷 Aclclouds 续期通知",
        "",
        f"❌ 续期状态未确认: {project_name}",
        f"👤 登录账户: {masked_email}",
    ]
    if old_expiry and old_expiry.lower() not in ['suspended', 'paused', '暂停']:
        lines.append(f"旧过期: {old_expiry}{old_remaining}")
    lines.extend([
        f"当前过期: {new_expiry}{new_remaining}",
        f"页面提示: {result_note or '未发现成功提示'}",
    ])
    return "\n".join(lines)

def handle_renew_antibot(sb, project_name):
    modal_selectors = [
        '//div[contains(., "Anti-bot confirmation")]',
        '//div[contains(., "Confirm you are human")]',
        '//div[contains(., "I am not a robot")]',
    ]

    for selector in modal_selectors:
        try:
            sb.wait_for_element_visible(selector, timeout=5)
            print(f"[{project_name}] 检测到续期人机验证窗口")
            return click_captcha_checkbox(sb, '续期人机验证', timeout=5)
        except Exception:
            continue

    print(f"[{project_name}] 未检测到续期人机验证窗口，继续等待续期结果")
    return False

def cancel_renew_antibot_dialog(sb):
    for selector in ['//div[@role="dialog"]//button[normalize-space(.)="Cancel"]',
                     '//button[normalize-space(.)="Cancel"]']:
        try:
            buttons = [b for b in sb.driver.find_elements(By.XPATH, selector) if b.is_displayed()]
            if buttons:
                safe_click_element(sb, buttons[0], '续期弹窗 Cancel')
                sb.sleep(1)
                return True
        except Exception:
            continue
    return False

def close_notifications_popup(sb, label='通知弹窗', timeout=8):
    dialog_selectors = [
        '//div[@role="dialog"][contains(@class, "NotificationModal")]',
        '//div[@role="dialog"][@aria-label="Notifications"]',
    ]
    dialog = None
    for selector in dialog_selectors:
        try:
            elems = [el for el in sb.driver.find_elements(By.XPATH, selector) if el.is_displayed()]
            if elems:
                dialog = elems[0]
                break
        except Exception:
            continue

    if dialog is None:
        print(f"未检测到{label}，跳过关闭。")
        return False

    button_xpaths = [
        './/button[contains(normalize-space(.), "Dismiss")]',
        './/button[contains(@class, "NotificationModalSecondaryAction")]',
        './/button[@aria-label="Fermer" or @aria-label="Close"]',
        './/button[contains(@class, "NotificationModalClose")]',
    ]
    for selector in button_xpaths:
        try:
            buttons = [b for b in dialog.find_elements(By.XPATH, selector) if b.is_displayed()]
        except Exception:
            continue
        if buttons:
            safe_click_element(sb, buttons[0], f'{label} 关闭按钮')
            sb.sleep(1)
            print(f"{label} 已关闭。")
            return True

    print(f"{label} 未找到可点击的关闭按钮。")
    return False

def find_dashboard_renew_buttons(sb):
    buttons = []
    for btn in sb.driver.find_elements(By.XPATH, '//button[normalize-space(.)="Renew"]'):
        try:
            if btn.is_displayed() and btn.is_enabled():
                buttons.append(btn)
        except Exception:
            continue
    return buttons

def get_dashboard_row_info(sb, renew_button):
    return sb.driver.execute_script(
        '''
        let node = arguments[0];
        for (let i = 0; i < 10 && node; i += 1, node = node.parentElement) {
          if (node.querySelector && node.querySelector('[data-label="ID"]') && node.querySelector('[data-label="Renewal"]')) {
            return node.innerText || '';
          }
        }
        return '';
        ''',
        renew_button,
    )

def parse_dashboard_row(row_text):
    lines = [line.strip() for line in (row_text or '').splitlines() if line.strip()]
    service_id = lines[0] if lines else ''
    project_name = lines[1] if len(lines) > 1 else (service_id or '未知服务')
    old_expiry = extract_date_like(row_text) or '未知'
    return project_name, service_id, old_expiry

def wait_for_dashboard_renew_result(sb, service_id, old_expiry, timeout=40):
    start_time = time.time()
    note = ''
    while time.time() - start_time < timeout:
        try:
            body_text = sb.driver.find_element(By.TAG_NAME, 'body').text or ''

            if has_renew_antibot_modal(sb):
                note = 'Cap 验证弹窗尚未关闭'
            elif 'No renewal is currently available' in body_text:
                return True, '续期列表已清空'
            elif service_id and service_id not in body_text:
                return True, '服务已从续期列表移除'
            else:
                renewing = [b for b in sb.driver.find_elements(
                    By.XPATH, '//button[contains(normalize-space(.), "Renewing")]') if b.is_displayed()]
                if renewing:
                    note = 'Renew 处理中...'
                elif find_dashboard_renew_buttons(sb):
                    new_date = extract_date_like(body_text)
                    if new_date and old_expiry != '未知' and new_date != old_expiry:
                        return True, f'续期日期已更新: {new_date}'
                    note = 'Renew 按钮仍在，等待结果...'
                else:
                    return True, 'Renew 按钮已消失'
        except Exception as e:
            note = f'检查续期结果时暂时失败: {e}'
        sb.sleep(1)
    return False, note or '等待续期结果超时'

def fetch_new_expiry_from_projects(sb, service_id, timeout=30):
    if not service_id:
        return '未知'
    try:
        sb.open(PROJECTS_URL)
        sb.wait_for_ready_state_complete()
        sb.sleep(3)
        xpath = f'//article[contains(normalize-space(.), "{service_id}")]'
        start_time = time.time()
        while time.time() - start_time < timeout:
            rows = [r for r in sb.driver.find_elements(By.XPATH, xpath) if r.is_displayed()]
            if rows:
                date_text = extract_date_like(element_text(rows[0]))
                if date_text:
                    return date_text
            sb.sleep(1)
        print(f"未在 My services 页面找到服务 {service_id} 的过期时间。")
    except Exception as e:
        print(f"读取新过期时间失败: {e}")
    return '未知'

def js_set_input_value(sb, selector, value):
    sb.execute_script(
        '''
        const el = document.querySelector(arguments[0]);
        if (!el) return false;
        el.focus();
        el.value = arguments[1];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        return true;
        ''',
        selector,
        value,
    )

def fill_input(sb, selector, value, label, timeout=15):
    sb.wait_for_element_visible(selector, timeout=timeout)
    scroll_to_selector(sb, selector)
    sb.click(selector)
    sb.clear(selector)
    sb.type(selector, value)

    entered_value = sb.get_value(selector)
    if label == '密码':
        print(f"{label}输入框当前值长度: {len(entered_value)}")
    else:
        print(f"{label}输入框当前值: '{entered_value}'")

    if entered_value != value:
        print(f"{label}输入未生效，使用 JavaScript 强制赋值并触发事件")
        js_set_input_value(sb, selector, value)
        entered_value = sb.get_value(selector)
        if label == '密码':
            print(f"JS 赋值后{label}长度: {len(entered_value)}")
        else:
            print(f"JS 赋值后{label}值: '{entered_value}'")

    return entered_value == value

def login(sb, email, password):
    print("开始登录流程...")

    if not fill_input(sb, '#username', email, '邮箱'):
        print("⚠️ 邮箱仍未能正确填入，可能页面有动态行为。")

    if not fill_input(sb, '#password', password, '密码'):
        print("⚠️ 密码仍未能正确填入。")

    captcha_ok = click_captcha_checkbox(sb, '登录验证码', timeout=15)
    if not captcha_ok:
        print("⚠️ 登录验证码未完成，暂不点击登录按钮，避免直接提交。")
        return False

    sb.sleep(2)

    login_page_url = sb.get_current_url()
    clicked = False

    for selector in ['button[type="submit"]', 'div.auth-submit-btn',
                     '//button[contains(text(), "Sign in")]',
                     '//div[contains(text(), "Sign in")]']:
        try:
            sb.wait_for_element_visible(selector, timeout=5)
            scroll_to_selector(sb, selector)
            sb.click(selector)
            clicked = True
            print(f"点击 Sign in 使用: {selector}")
            break
        except Exception as e:
            print(f"选择器 {selector} 失败: {e}")
    if not clicked:
        print("所有选择器失败，使用 JS 点击")
        sb.execute_script('''
            var els = document.querySelectorAll('div, button, a');
            for (var el of els) {
                if (el.textContent.trim() === 'Sign in') {
                    el.click();
                    return true;
                }
            }
            return false;
        ''')

    try:
        wait_for_url_change(sb, login_page_url, timeout=30)
        if '/auth/login' not in sb.get_current_url():
            print(f"✅ 登录成功！当前页面: {sb.get_title()} (URL: {sb.get_current_url()})")
            return True
        else:
            error_msg = ""
            try:
                errors = sb.driver.find_elements(By.CSS_SELECTOR, '.auth-error-text, .alert-danger, .error-message')
                error_msg = errors[0].text.strip() if errors else ''
            except:
                pass
            print(f"❌ 登录失败，错误: {error_msg}")
            return False
    except Exception as e:
        print(f"登录过程异常: {e}")
        return False
    
def get_current_ip(proxy_server: str = "") -> str:
    proxies = None
    if proxy_server:
        proxies = {"http": proxy_server, "https": proxy_server}
    response = requests.get("https://api.ip.sb/ip", proxies=proxies, timeout=15)
    response.raise_for_status()
    return response.text.strip()

def main():

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    PROXY_SERVER = os.getenv('S5_PROXY') or os.getenv('PROXY_SERVER') or "socks://127.0.0.1:1080"

    sb_options = {'uc': True, 'headless': False}
    if IS_PROXY:
        sb_options['proxy'] = PROXY_SERVER
        print(f"🔗 挂载代理: {PROXY_SERVER}")
    else:
        print("🍭 未使用代理，直连访问")

    with SB(**sb_options) as sb:
        try:
            ip = get_current_ip(PROXY_SERVER if IS_PROXY else "")
            print(f"📍 当前出口IP: {ip}")
        except Exception as e:
            print(f"获取出口IP失败: {e}")

        sb.set_window_size(1366, 768)

        sb.open(LOGIN_URL)
        sb.wait_for_ready_state_complete()
        time.sleep(2)

        if is_login_page(sb):
            print("执行正常登录...")
            if not EMAIL or not PASSWORD:
                print("❌ 未配置 ACL_EMAIL 或 ACL_PASSWORD，无法执行账号密码登录。")
                send_telegram("⚠️ 未配置 ACL_EMAIL 或 ACL_PASSWORD。")
                return
            if not login(sb, EMAIL, PASSWORD):
                send_telegram(f"⚠️ ACLClouds 登录失败，请检查账号密码或网站状态。\n运行时间: {beijing_time_str()}")
                return
        elif is_logged_in(sb):
            print(f"✅ 当前已登录。URL: {sb.get_current_url()}，标题: {sb.get_title()}")
        else:
            print(f"❌ 未能确认登录状态。URL: {sb.get_current_url()}，标题: {sb.get_title()}")
            send_telegram("⚠️ 未能确认登录状态，请检查账号密码配置。")
            return

        # =========================================================================
        # 处理续期逻辑（兼容旧版直接 Renew 和新版需要点 Manage 进详情的情况）
        # =========================================================================
        sb.open(DASHBOARD_URL)
        sb.wait_for_ready_state_complete()
        time.sleep(3)
        close_notifications_popup(sb)

        processed = 0
        max_services = 10
        
        # 1. 尝试在 Dashboard 处理老版本的直接 Renew 按钮
        while processed < max_services:
            renew_buttons = find_dashboard_renew_buttons(sb)
            if not renew_buttons:
                break

            row_text = get_dashboard_row_info(sb, renew_buttons[0])
            project_name, service_id, old_expiry = parse_dashboard_row(row_text)
            print(f"[{project_name}] 当前过期: {old_expiry}（服务ID: {service_id or '未知'}）")

            try:
                safe_click_element(sb, renew_buttons[0], f"[{project_name}] Renew按钮")
                print(f"[{project_name}] 点击 Renew...")
                captcha_ok = handle_renew_antibot(sb, project_name)
                if not captcha_ok:
                    print(f"[{project_name}] Cap 验证未完成，尝试点击 Cancel 关闭弹窗。")
                    cancel_renew_antibot_dialog(sb)

                success, result_note = wait_for_dashboard_renew_result(sb, service_id, old_expiry, timeout=40)
                if success:
                    new_expiry = fetch_new_expiry_from_projects(sb, service_id)
                    print(f"续期成功！状态: {result_note}，新过期: {new_expiry}")
                    send_telegram(build_success_message(project_name, old_expiry, new_expiry))
                    sb.open(DASHBOARD_URL)
                    sb.wait_for_ready_state_complete()
                    time.sleep(2)
                else:
                    print(f"续期状态未确认: {result_note}")
                    send_telegram(build_unconfirmed_message(project_name, old_expiry, old_expiry, result_note))
            except Exception as e:
                print(f"处理 [{project_name}] 出错: {e}")
                send_telegram(f"🇫🇷 Aclclouds 续期通知\n\n⚠️ 处理出错: {str(e)}")
            processed += 1

        # 2. 如果 Dashboard 没有直接的 Renew 按钮 (processed == 0)，前往 My services 页面找卡片
        if processed == 0:
            print("未在 Dashboard 找到直接的 Renew 按钮，前往 My services 页面查找...")
            sb.open(PROJECTS_URL)
            sb.wait_for_ready_state_complete()
            time.sleep(3)
            
            visited_projects = set()
            
            while processed < max_services:
                cards = find_project_cards(sb)
                if not cards:
                    print("My services 页面未找到服务卡片。")
                    break
                    
                found_action = False
                for card in cards:
                    try:
                        card_text = element_text(card)
                        lines = [line.strip() for line in card_text.splitlines() if line.strip()]
                        project_name = lines[0] if lines else f"未知_{processed}"
                        old_expiry = extract_date_like(card_text) or '未知'
                        
                        if project_name in visited_projects:
                            continue
                            
                        # 先尝试找直接的 Renew 按钮
                        btns = find_renew_buttons(card)
                        if btns:
                            print(f"[{project_name}] 在 My services 找到直接续期按钮，点击...")
                            safe_click_element(sb, btns[0], f"[{project_name}] Renew")
                            captcha_ok = handle_renew_antibot(sb, project_name)
                            if not captcha_ok:
                                cancel_renew_antibot_dialog(sb)
                            sb.sleep(5)
                            send_telegram(build_success_message(project_name, old_expiry, "已点击续期，请确认"))
                            visited_projects.add(project_name)
                            processed += 1
                            found_action = True
                            sb.open(PROJECTS_URL)
                            sb.wait_for_ready_state_complete()
                            time.sleep(3)
                            break # 重新获取卡片列表
                            
                        # 如果没有 Renew 按钮，尝试找 Manage 按钮进入详情页
                        manage_btns = card.find_elements(By.XPATH, './/a[contains(normalize-space(.), "Manage")] | .//button[contains(normalize-space(.), "Manage")]')
                        valid_manage = [b for b in manage_btns if b.is_displayed()]
                        
                        if valid_manage:
                            print(f"[{project_name}] 未找到直接续期按钮，点击 Manage 进入详情页寻找...")
                            visited_projects.add(project_name)
                            
                            manage_url = valid_manage[0].get_attribute('href')
                            if manage_url:
                                if manage_url.startswith('/'):
                                    manage_url = BASE_URL + manage_url
                                sb.open(manage_url)
                            else:
                                safe_click_element(sb, valid_manage[0], f"[{project_name}] Manage")
                            
                            sb.wait_for_ready_state_complete()
                            time.sleep(3)
                            
                            # 在详情页找 Renew
                            detail_btns = find_renew_buttons(sb.driver)
                            
                            # 尝试从详情页提取旧时间
                            body_text_before = sb.driver.find_element(By.TAG_NAME, 'body').text
                            detail_old_expiry = extract_date_like(body_text_before) or old_expiry
                            
                            if detail_btns:
                                print(f"[{project_name}] 详情页找到续期按钮，点击...")
                                safe_click_element(sb, detail_btns[0], f"[{project_name}] 详情页 Renew")
                                captcha_ok = handle_renew_antibot(sb, project_name)
                                if not captcha_ok:
                                    cancel_renew_antibot_dialog(sb)
                                sb.sleep(5)
                                
                                # 尝试获取新时间
                                body_text_after = sb.driver.find_element(By.TAG_NAME, 'body').text
                                detail_new_expiry = extract_date_like(body_text_after) or "已点击续期，请确认"
                                
                                send_telegram(build_success_message(project_name, detail_old_expiry, detail_new_expiry))
                                processed += 1
                            else:
                                print(f"[{project_name}] 详情页未找到续期按钮。")
                                
                            # 返回列表页
                            sb.open(PROJECTS_URL)
                            sb.wait_for_ready_state_complete()
                            time.sleep(3)
                            found_action = True
                            break # 重新获取卡片列表
                            
                    except Exception as e:
                        print(f"处理卡片出错: {e}")
                        sb.open(PROJECTS_URL)
                        sb.wait_for_ready_state_complete()
                        time.sleep(2)
                        continue
                
                if not found_action:
                    print("所有卡片已检查完毕，未发现可处理的续期。")
                    break

        if processed == 0:
            body_text = ''
            try:
                sb.open(DASHBOARD_URL)
                sb.wait_for_ready_state_complete()
                time.sleep(2)
                body_text = sb.driver.find_element(By.TAG_NAME, 'body').text
            except Exception:
                pass
            
            if 'No renewal is currently available' in body_text or '0 to renew' in body_text:
                print("当前没有可续期的服务。")
                send_telegram(build_not_yet_due_message('（无待续期服务）', 'No renewal is currently available'))
            else:
                print("❌ 既未在 dashboard 也未在详情页找到续期按钮。")
                log_projects_page_diagnostics(sb)
                send_telegram("⚠️ 未能找到 Renew 按钮，请检查页面结构。")

        print("所有项目处理完成。")

if __name__ == '__main__':
    main()
