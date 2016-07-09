import json
import urllib.parse

import aiohttp
from src.exceptions import VkAuthError, VkCaptchaNeeded, VkTwoFactorCodeNeeded
from src.parser import AuthPageParser, TwoFactorCodePageParser


class AuthSession:
    AUTH_URL = 'https://oauth.vk.com/authorize'
    timeout = 10
    API_VERSION = '5.52'

    def __init__(self, login, password, app_id, scope=None):
        self.login = login
        self.password = password
        self.app_id = app_id
        self.scope = scope
        self.session = aiohttp.ClientSession()

    async def fetch(self, url, params):
        with aiohttp.Timeout(self.timeout):
            response = await self.session.get(url, params=params)
            return response.status, await response.text()

    async def post(self, url, data):
        with aiohttp.Timeout(self.timeout):
            response = await self.session.post(url, data=data)
            return response.url, await response.text()

    async def authorize(self):
        """
        2 attempts for each step
        :return: access token
        """
        # TODO: make several attempts for each step
        html = await self.get_auth_page()
        url, html = await self.process_auth_form(html)
        q = urllib.parse.urlparse(url)
        if q.path == '/authorize':
            url, html = await self.process_auth_form(html)
            q = urllib.parse.urlparse(url)
        if q.path == '/login':
            url, html = await self.process_2auth_form(html)
            q = urllib.parse.urlparse(url)
        if q.path == '/login':
            url, html = await self.process_2auth_form(html)
            q = urllib.parse.urlparse(url)
        if q.path == '/blank.html':
            qs = dict(urllib.parse.parse_qsl(q.fragment))
            return qs['access_token']

    async def get_auth_page(self):
        params = {'client_id': self.app_id,
                  'redirect_uri': 'https://oauth.vk.com/blank.html',
                  'display': 'mobile',
                  'response_type': 'token',
                  'v': self.API_VERSION
                  }

        if self.scope is not None:
            params['scope'] = self.scope
        status, response = await self.fetch(self.AUTH_URL, params)
        if status != 200:
            error_dict = json.loads(response)
            raise VkAuthError(error_dict['error'], error_dict['error_description'], self.AUTH_URL, params)
        return response

    async def process_auth_form(self, html):
        p = AuthPageParser()
        p.feed(html)
        p.close()
        form_data = dict(p.inputs)
        form_url = p.url
        form_data['email'] = self.login
        form_data['pass'] = self.password
        if p.message:
            raise VkAuthError('invalid_data', p.message, form_url, form_data)
        elif p.captcha_url:
            form_data['captcha_key'] = await self.enter_captcha(p.captcha_url, form_data['captcha_sid'])
        url, html = await self.post(form_url, form_data)
        return url, html

    async def process_2auth_form(self, html):
        p = TwoFactorCodePageParser()
        p.feed(html)
        p.close()
        form_url = p.url
        form_data = dict(p.inputs)
        form_data['remember'] = 0
        if p.message:
            raise VkAuthError('invalid_data', p.message, form_url, form_data)
        form_data['code'] = await self.enter_confirmation_сode()
        url, html = await self.post(form_url, form_data)
        return url, html

    async def enter_captcha(self, url, sid):
        """
        Override this method for processing captcha.
        :return captcha value
        """
        raise VkCaptchaNeeded(url, sid)

    async def enter_confirmation_сode(self):
        """
        Override this method for processing confirmation 2uth code.
        :return confirmation code
        """
        raise VkTwoFactorCodeNeeded()

    def close(self):
        self.session.close()



