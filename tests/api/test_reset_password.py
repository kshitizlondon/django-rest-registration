import time
from unittest.mock import patch

from django.test.utils import override_settings
from rest_framework import status

from rest_registration.api.views import (
    reset_password,
    send_reset_password_link,
)
from rest_registration.api.views.reset_password import ResetPasswordSigner
from .base import APIViewTestCase


RESET_PASSWORD_VERIFICATION_URL = '/reset-password/'


@override_settings(
    REST_REGISTRATION={
        'RESET_PASSWORD_VERIFICATION_URL': RESET_PASSWORD_VERIFICATION_URL,
    },
)
class BaseResetPasswordViewTestCase(APIViewTestCase):
    pass


class SendResetPasswordLinkViewTestCase(BaseResetPasswordViewTestCase):

    def test_send_link_ok(self):
        user = self.create_test_user(username='testusername')
        request = self.factory.post('', {
            'login': user.username,
        })
        with self.assert_mail_sent():
            response = send_reset_password_link(request)
        self.assert_valid_response(response, status.HTTP_200_OK)

    def test_send_link_invalid_login(self):
        user = self.create_test_user(username='testusername')
        request = self.factory.post('', {
            'login': user.username + 'b',
        })
        with self.assert_mails_sent(0):
            response = send_reset_password_link(request)
        self.assert_invalid_response(response, status.HTTP_400_BAD_REQUEST)


class ResetPasswordViewTestCase(BaseResetPasswordViewTestCase):

    def test_reset_ok(self):
        old_password = 'password1'
        new_password = 'password2'
        user = self.create_test_user(password=old_password)
        signer = ResetPasswordSigner({'user_id': user.pk})
        data = signer.get_signed_data()
        data['password'] = new_password
        request = self.factory.post('', data)
        response = reset_password(request)
        self.assert_response_is_ok(response)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    def test_reset_short_password(self):
        old_password = 'password1'
        new_password = 'c'
        user = self.create_test_user(password=old_password)
        signer = ResetPasswordSigner({'user_id': user.pk})
        data = signer.get_signed_data()
        data['password'] = new_password
        request = self.factory.post('', data)
        response = reset_password(request)
        self.assert_response_is_bad_request(response)
        user.refresh_from_db()
        self.assertTrue(user.check_password(old_password))

    def test_reset_numeric_password(self):
        old_password = 'password1'
        new_password = '563495763456'
        user = self.create_test_user(password=old_password)
        signer = ResetPasswordSigner({'user_id': user.pk})
        data = signer.get_signed_data()
        data['password'] = new_password
        request = self.factory.post('', data)
        response = reset_password(request)
        self.assert_response_is_bad_request(response)
        user.refresh_from_db()
        self.assertTrue(user.check_password(old_password))

    def test_reset_password_same_as_username(self):
        username = 'albert.einstein'
        old_password = 'password1'
        new_password = username
        user = self.create_test_user(username=username, password=old_password)
        signer = ResetPasswordSigner({'user_id': user.pk})
        data = signer.get_signed_data()
        data['password'] = new_password
        request = self.factory.post('', data)
        response = reset_password(request)
        self.assert_response_is_bad_request(response)
        user.refresh_from_db()
        self.assertTrue(user.check_password(old_password))

    def test_reset_tampered_timestamp(self):
        old_password = 'password1'
        new_password = 'password2'
        user = self.create_test_user(password=old_password)
        signer = ResetPasswordSigner({'user_id': user.pk})
        data = signer.get_signed_data()
        data['timestamp'] += 1
        data['password'] = new_password
        request = self.factory.post('', data)
        response = reset_password(request)
        self.assert_invalid_response(response, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertTrue(user.check_password(old_password))

    def test_reset_expired(self):
        timestamp = int(time.time())
        old_password = 'password1'
        new_password = 'password2'
        user = self.create_test_user(password=old_password)
        with patch('time.time',
                   side_effect=lambda: timestamp):
            signer = ResetPasswordSigner({'user_id': user.pk})
            data = signer.get_signed_data()
        data['password'] = new_password
        request = self.factory.post('', data)
        with patch('time.time',
                   side_effect=lambda: timestamp + 3600 * 24 * 8):
            response = reset_password(request)
        self.assert_invalid_response(response, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertTrue(user.check_password(old_password))
