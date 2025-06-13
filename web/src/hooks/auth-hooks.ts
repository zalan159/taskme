import userService from '@/services/user-service';
import authorizationUtil from '@/utils/authorization-util';
import { message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'umi';

interface UserInfoResponse {
  code: number;
  data?: {
    id: string;
    [key: string]: any;
  };
}

export const useLoginWithGithub = () => {
  const [currentQueryParameters, setSearchParams] = useSearchParams();
  const error = currentQueryParameters.get('error');
  const newQueryParameters: URLSearchParams = useMemo(
    () => new URLSearchParams(currentQueryParameters.toString()),
    [currentQueryParameters],
  );
  const navigate = useNavigate();

  if (error) {
    message.error(error);
    navigate('/login');
    newQueryParameters.delete('error');
    setSearchParams(newQueryParameters);
    return;
  }

  const auth = currentQueryParameters.get('auth');

  if (auth) {
    authorizationUtil.setAuthorization(auth);
    newQueryParameters.delete('auth');
    setSearchParams(newQueryParameters);

    // Fetch user information and set userId in localStorage
    userService
      .user_info()
      .then(({ data }: { data: UserInfoResponse }) => {
        if (data.code === 0 && data.data) {
          authorizationUtil.setItems({
            userId: data.data.id,
          });
        }
      })
      .catch((error: Error) => {
        console.error('Failed to fetch user info after login:', error);
      });
  }
  return auth;
};

export const useAuth = () => {
  const auth = useLoginWithGithub();
  const [isLogin, setIsLogin] = useState<Nullable<boolean>>(null);

  useEffect(() => {
    setIsLogin(!!authorizationUtil.getAuthorization() || !!auth);
  }, [auth]);

  return { isLogin };
};
