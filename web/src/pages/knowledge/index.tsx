import { useInfiniteFetchKnowledgeList } from '@/hooks/knowledge-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import {
  Button,
  Divider,
  Empty,
  Flex,
  Input,
  Skeleton,
  Space,
  Typography,
} from 'antd';
import { useTranslation } from 'react-i18next';
import InfiniteScroll from 'react-infinite-scroll-component';
import { useSaveKnowledge } from './hooks';
import KnowledgeCard from './knowledge-card';
import KnowledgeCreatingModal from './knowledge-creating-modal';

import { useMemo } from 'react';
import styles from './index.less';

const { Title } = Typography;

const KnowledgeList = () => {
  const { data: userInfo } = useFetchUserInfo();
  const { t } = useTranslation('translation', { keyPrefix: 'knowledgeList' });
  const {
    visible,
    hideModal,
    showModal,
    onCreateOk,
    loading: creatingLoading,
  } = useSaveKnowledge();
  const {
    fetchNextPage,
    data,
    hasNextPage,
    searchString,
    handleInputChange,
    loading,
  } = useInfiniteFetchKnowledgeList();

  const groupedKnowledge = useMemo(() => {
    const list =
      data?.pages?.flatMap((x) => (Array.isArray(x.kbs) ? x.kbs : [])) ?? [];
    return {
      public: list.filter((item) => item.permission === 'public'),
      team: list.filter((item) => item.permission === 'team'),
      me: list.filter((item) => item.permission === 'me'),
    };
  }, [data?.pages]);

  const total = useMemo(() => {
    return data?.pages.at(-1).total ?? 0;
  }, [data?.pages]);

  const renderKnowledgeSection = (title: string, items: any[]) => {
    if (items.length === 0) return null;

    return (
      <div className={styles.section}>
        <Title level={4} className={styles.sectionTitle}>
          {title}
        </Title>
        <Flex gap={'large'} wrap="wrap">
          {items.map((item: any, index: number) => (
            <KnowledgeCard item={item} key={`${item?.name}-${index}`} />
          ))}
        </Flex>
        <Divider />
      </div>
    );
  };

  return (
    <Flex className={styles.knowledge} vertical flex={1} id="scrollableDiv">
      <div className={styles.topWrapper}>
        <div>
          <span className={styles.title}>
            {t('welcome')}, {userInfo.nickname}
          </span>
          <p className={styles.description}>{t('description')}</p>
        </div>
        <Space size={'large'}>
          <Input
            placeholder={t('searchKnowledgePlaceholder')}
            value={searchString}
            style={{ width: 220 }}
            allowClear
            onChange={handleInputChange}
            prefix={<SearchOutlined />}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={showModal}
            className={styles.topButton}
          >
            {t('createKnowledgeBase')}
          </Button>
        </Space>
      </div>
      <div className={styles.knowledgeCardContainer}>
        <InfiniteScroll
          dataLength={Object.values(groupedKnowledge).flat().length}
          next={fetchNextPage}
          hasMore={hasNextPage}
          loader={<Skeleton avatar paragraph={{ rows: 1 }} active />}
          endMessage={!!total && <Divider plain>{t('noMoreData')} 🤐</Divider>}
          scrollableTarget="scrollableDiv"
        >
          {loading ? (
            <Skeleton avatar paragraph={{ rows: 1 }} active />
          ) : Object.values(groupedKnowledge).flat().length > 0 ? (
            <>
              {renderKnowledgeSection(
                t('publicKnowledge'),
                groupedKnowledge.public,
              )}
              {renderKnowledgeSection(
                t('teamKnowledge'),
                groupedKnowledge.team,
              )}
              {renderKnowledgeSection(
                t('privateKnowledge'),
                groupedKnowledge.me,
              )}
            </>
          ) : (
            <Empty className={styles.knowledgeEmpty} />
          )}
        </InfiniteScroll>
      </div>
      <KnowledgeCreatingModal
        loading={creatingLoading}
        visible={visible}
        hideModal={hideModal}
        onOk={onCreateOk}
      />
    </Flex>
  );
};

export default KnowledgeList;
