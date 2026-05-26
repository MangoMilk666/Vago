package com.vago.user.service;

import com.vago.user.model.dto.*;
import com.vago.user.model.vo.*;

public interface UserService {

    void sendSmsCode(SmsSendDTO dto);

    LoginVO register(UserRegisterDTO dto);

    LoginVO loginByPhone(UserLoginPhoneDTO dto);

    LoginVO loginByOAuth(UserLoginOAuthDTO dto);

    TokenVO refreshToken(TokenRefreshDTO dto);

    void logout(String accessToken);

    UserVO getProfile(String userUuid);

    UserVO updateProfile(String userUuid, UserUpdateProfileDTO dto);

    UserSettingsVO getSettings(String userUuid);

    UserSettingsVO updateSettings(String userUuid, UserUpdateSettingsDTO dto);

    String cancelAccount(String userUuid, AccountCancelDTO dto);

    void revokeCancelAccount(String userUuid);
}
