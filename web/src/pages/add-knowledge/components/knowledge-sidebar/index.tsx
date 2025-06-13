import { ReactComponent as ConfigurationIcon } from '@/assets/svg/knowledge-configration.svg';
import { ReactComponent as DatasetIcon } from '@/assets/svg/knowledge-dataset.svg';
import { ReactComponent as TestingIcon } from '@/assets/svg/knowledge-testing.svg';
import {
  useFetchKnowledgeBaseConfiguration,
  useFetchKnowledgeGraph,
} from '@/hooks/knowledge-hooks';
import {
  useGetKnowledgeSearchParams,
  useSecondPathName,
} from '@/hooks/route-hook';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { getWidth } from '@/utils';
import { Avatar, Menu, MenuProps, Space } from 'antd';
import classNames from 'classnames';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'umi';
import { KnowledgeRouteKey } from '../../constant';

import { isEmpty } from 'lodash';
import { GitGraph } from 'lucide-react';
import styles from './index.less';

const KnowledgeSidebar = () => {
  let navigate = useNavigate();
  const activeKey = useSecondPathName();
  const { knowledgeId } = useGetKnowledgeSearchParams();

  const [windowWidth, setWindowWidth] = useState(getWidth());
  const [collapsed, setCollapsed] = useState(false);
  const { t } = useTranslation();
  const {
    data: knowledgeDetails,
    loading: knowledgeLoading,
    error: knowledgeError,
  } = useFetchKnowledgeBaseConfiguration();
  const { data: userInfo } = useFetchUserInfo();

  const { data } = useFetchKnowledgeGraph();

  const isCreator = useMemo(() => {
    // If knowledge details is loading or has error, don't show configuration button
    if (knowledgeLoading || knowledgeError) {
      console.log(
        'Knowledge base is loading or has error - hiding configuration button',
      );
      return false;
    }

    // If knowledgeDetails is empty, we should not show the configuration button
    if (!knowledgeDetails || Object.keys(knowledgeDetails).length === 0) {
      console.log(
        'Knowledge details is empty or undefined - hiding configuration button',
      );
      return false;
    }

    const result = !!(
      userInfo?.id &&
      knowledgeDetails?.created_by &&
      userInfo.id === knowledgeDetails.created_by
    );

    return result;
  }, [userInfo, knowledgeDetails, knowledgeLoading, knowledgeError]);

  // Debug logs for data
  useEffect(() => {
    console.log('KnowledgeSidebar - Knowledge Details:', knowledgeDetails);
    console.log('KnowledgeSidebar - User Info:', userInfo);
    console.log('KnowledgeSidebar - Knowledge Graph Data:', data);
    console.log('KnowledgeSidebar - Is Creator:', isCreator);
    console.log('KnowledgeSidebar - Graph Not Empty:', !isEmpty(data?.graph));
  }, [
    knowledgeDetails,
    userInfo,
    knowledgeId,
    knowledgeLoading,
    knowledgeError,
    data,
    isCreator,
  ]);

  const handleSelect: MenuProps['onSelect'] = (e) => {
    navigate(`/knowledge/${e.key}?id=${knowledgeId}`);
  };

  type MenuItem = Required<MenuProps>['items'][number];

  const getItem = useCallback(
    (
      label: string,
      key: React.Key,
      icon?: React.ReactNode,
      disabled?: boolean,
      children?: MenuItem[],
      type?: 'group',
    ): MenuItem => {
      return {
        key,
        icon,
        children,
        label: t(`knowledgeDetails.${label}`),
        type,
        disabled,
      } as MenuItem;
    },
    [t],
  );

  const items: MenuItem[] = useMemo(() => {
    const list = [
      getItem(
        KnowledgeRouteKey.Dataset,
        KnowledgeRouteKey.Dataset,
        <DatasetIcon />,
      ),
      getItem(
        KnowledgeRouteKey.Testing,
        KnowledgeRouteKey.Testing,
        <TestingIcon />,
      ),
    ];

    // 始终显示知识图谱菜单项 - 所有用户都可以查看，不管graph数据是否为空
    list.push(
      getItem(
        KnowledgeRouteKey.KnowledgeGraph,
        KnowledgeRouteKey.KnowledgeGraph,
        <GitGraph />,
      ),
    );

    // 只有创建者可以看到配置菜单项
    if (isCreator) {
      list.push(
        getItem(
          KnowledgeRouteKey.Configuration,
          KnowledgeRouteKey.Configuration,
          <ConfigurationIcon />,
        ),
      );
    }

    return list;
  }, [getItem, isCreator]);

  useEffect(() => {
    if (windowWidth.width > 957) {
      setCollapsed(false);
    } else {
      setCollapsed(true);
    }
  }, [windowWidth.width]);

  useEffect(() => {
    const widthSize = () => {
      const width = getWidth();

      setWindowWidth(width);
    };
    window.addEventListener('resize', widthSize);
    return () => {
      window.removeEventListener('resize', widthSize);
    };
  }, []);

  return (
    <div className={styles.sidebarWrapper}>
      <div className={styles.sidebarTop}>
        <Space size={8} direction="vertical">
          <Avatar size={64} src={knowledgeDetails.avatar} />
          <div className={styles.knowledgeTitle}>{knowledgeDetails.name}</div>
        </Space>
        <p className={styles.knowledgeDescription}>
          {knowledgeDetails.description}
        </p>
      </div>
      <div className={styles.divider}></div>
      <div className={styles.menuWrapper}>
        <Menu
          selectedKeys={[activeKey]}
          // mode="inline"
          className={classNames(styles.menu, {
            [styles.defaultWidth]: windowWidth.width > 957,
            [styles.minWidth]: windowWidth.width <= 957,
          })}
          // inlineCollapsed={collapsed}
          items={items}
          onSelect={handleSelect}
        />
      </div>
    </div>
  );
};

export default KnowledgeSidebar;
