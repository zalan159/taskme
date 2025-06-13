import ChunkMethodModal from '@/components/chunk-method-modal';
import SvgIcon from '@/components/svg-icon';
import { DocumentParserType } from '@/constants/knowledge';
import {
  useFetchNextDocumentList,
  useSetNextDocumentStatus,
} from '@/hooks/document-hooks';
import { useSetSelectedRecord } from '@/hooks/logic-hooks';
import { useSelectParserList } from '@/hooks/user-setting-hooks';
import { getExtension } from '@/utils/document-util';
import { Divider, Flex, Input, Switch, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useTranslation } from 'react-i18next';
import CreateFileModal from './create-file-modal';
import DocumentToolbar from './document-toolbar';
import {
  useChangeDocumentParser,
  useCreateEmptyDocument,
  useGetRowSelection,
  useHandleUploadDocument,
  useHandleWebCrawl,
  useNavigateToOtherPage,
  useRenameDocument,
  useShowMetaModal,
} from './hooks';
import ParsingActionCell from './parsing-action-cell';
import ParsingStatusCell from './parsing-status-cell';
import RenameModal from './rename-modal';
import WebCrawlModal from './web-crawl-modal';

import FileUploadModal from '@/components/file-upload-modal';
import { useFetchKnowledgeBaseConfiguration } from '@/hooks/knowledge-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { IDocumentInfo } from '@/interfaces/database/document';
import { formatDate } from '@/utils/date';
import { SearchOutlined } from '@ant-design/icons';
import { useMemo } from 'react';
import styles from './index.less';
import { SetMetaModal } from './set-meta-modal';

const { Text } = Typography;

const KnowledgeFile = () => {
  const { searchString, documents, pagination, handleInputChange } =
    useFetchNextDocumentList();
  const parserList = useSelectParserList();
  const { setDocumentStatus } = useSetNextDocumentStatus();
  const { toChunk } = useNavigateToOtherPage();
  const { currentRecord, setRecord } = useSetSelectedRecord<IDocumentInfo>();
  const {
    renameLoading,
    onRenameOk,
    renameVisible,
    hideRenameModal,
    showRenameModal,
  } = useRenameDocument(currentRecord.id);
  const {
    createLoading,
    onCreateOk,
    createVisible,
    hideCreateModal,
    showCreateModal,
  } = useCreateEmptyDocument();
  const {
    changeParserLoading,
    onChangeParserOk,
    changeParserVisible,
    hideChangeParserModal,
    showChangeParserModal,
  } = useChangeDocumentParser(currentRecord.id);
  const {
    documentUploadVisible,
    hideDocumentUploadModal,
    showDocumentUploadModal,
    onDocumentUploadOk,
    documentUploadLoading,
    uploadFileList,
    setUploadFileList,
    uploadProgress,
    setUploadProgress,
  } = useHandleUploadDocument();
  const {
    webCrawlUploadVisible,
    hideWebCrawlUploadModal,
    showWebCrawlUploadModal,
    onWebCrawlUploadOk,
    webCrawlUploadLoading,
  } = useHandleWebCrawl();
  const { t } = useTranslation('translation', {
    keyPrefix: 'knowledgeDetails',
  });

  const {
    showSetMetaModal,
    hideSetMetaModal,
    setMetaVisible,
    setMetaLoading,
    onSetMetaModalOk,
  } = useShowMetaModal(currentRecord.id);

  const rowSelection = useGetRowSelection();

  const { data: knowledgeDetails } = useFetchKnowledgeBaseConfiguration();
  const { data: userInfo } = useFetchUserInfo();

  const isCreator = useMemo(() => {
    return !!(
      userInfo?.id &&
      knowledgeDetails?.created_by &&
      userInfo.id === knowledgeDetails.created_by
    );
  }, [userInfo, knowledgeDetails]);

  const columns = useMemo(() => {
    const baseColumns: Array<Record<string, any>> = [
      {
        title: t('name'),
        dataIndex: 'name',
        key: 'name',
        fixed: 'left' as const,
        render: (text: string, record: IDocumentInfo) => (
          <div className={styles.toChunks} onClick={() => toChunk(record.id)}>
            <Flex gap={10} align="center">
              {record.thumbnail ? (
                <img className={styles.img} src={record.thumbnail} alt="" />
              ) : (
                <SvgIcon
                  name={`file-icon/${getExtension(record.name)}`}
                  width={24}
                ></SvgIcon>
              )}
              <Text ellipsis={{ tooltip: text }} className={styles.nameText}>
                {text}
              </Text>
            </Flex>
          </div>
        ),
      },
      {
        title: t('chunkNumber'),
        dataIndex: 'chunk_num',
        key: 'chunk_num',
      },
      {
        title: t('uploadDate'),
        dataIndex: 'create_time',
        key: 'create_time',
        render(value: number) {
          return formatDate(value);
        },
      },
      {
        title: t('chunkMethod'),
        dataIndex: 'parser_id',
        key: 'parser_id',
        render: (text: string) => {
          return parserList.find((x) => x.value === text)?.label;
        },
      },
    ];

    // Only show these columns for creators
    if (isCreator) {
      baseColumns.push(
        {
          title: t('enabled'),
          key: 'status',
          dataIndex: 'status',
          render: (_: unknown, record: IDocumentInfo) => (
            <>
              <Switch
                checked={record.status === '1'}
                onChange={(e) => {
                  setDocumentStatus({ status: e, documentId: record.id });
                }}
              />
            </>
          ),
        },
        {
          title: t('parsingStatus'),
          dataIndex: 'run',
          key: 'run',
          render: (_: unknown, record: IDocumentInfo) => {
            return <ParsingStatusCell record={record}></ParsingStatusCell>;
          },
        },
        {
          title: t('action'),
          key: 'action',
          render: (_: unknown, record: IDocumentInfo) => (
            <ParsingActionCell
              setCurrentRecord={setRecord}
              showRenameModal={showRenameModal}
              showChangeParserModal={showChangeParserModal}
              showSetMetaModal={showSetMetaModal}
              record={record}
            ></ParsingActionCell>
          ),
        },
      );
    }

    return baseColumns;
  }, [
    t,
    isCreator,
    setRecord,
    showRenameModal,
    showChangeParserModal,
    showSetMetaModal,
    setDocumentStatus,
  ]);

  const finalColumns = columns.map((x) => ({
    ...x,
    className: `${styles.column}`,
  })) as ColumnsType<IDocumentInfo>;

  return (
    <div className={styles.datasetWrapper}>
      <h3>{t('dataset')}</h3>
      <p>{t('datasetDescription')}</p>
      <Divider></Divider>

      {isCreator ? (
        <DocumentToolbar
          selectedRowKeys={rowSelection.selectedRowKeys as string[]}
          showCreateModal={showCreateModal}
          showWebCrawlModal={showWebCrawlUploadModal}
          showDocumentUploadModal={showDocumentUploadModal}
          searchString={searchString}
          handleInputChange={handleInputChange}
        />
      ) : (
        <div className={styles.filter}>
          <div></div> {/* 空元素用于保持Flex布局 */}
          <Input
            placeholder={t('searchFiles')}
            value={searchString}
            style={{ width: 220 }}
            allowClear
            onChange={handleInputChange}
            prefix={<SearchOutlined />}
          />
        </div>
      )}

      <Table
        rowKey="id"
        columns={finalColumns}
        dataSource={documents}
        pagination={pagination}
        rowSelection={isCreator ? rowSelection : undefined}
        className={styles.documentTable}
        scroll={{ scrollToFirstRowOnChange: true, x: 1300 }}
      />
      <CreateFileModal
        visible={createVisible}
        hideModal={hideCreateModal}
        loading={createLoading}
        onOk={onCreateOk}
      />
      <ChunkMethodModal
        documentId={currentRecord.id}
        parserId={currentRecord.parser_id as DocumentParserType}
        parserConfig={currentRecord.parser_config}
        documentExtension={getExtension(currentRecord.name)}
        onOk={onChangeParserOk}
        visible={changeParserVisible}
        hideModal={hideChangeParserModal}
        loading={changeParserLoading}
      />
      <RenameModal
        visible={renameVisible}
        onOk={onRenameOk}
        loading={renameLoading}
        hideModal={hideRenameModal}
        initialName={currentRecord.name}
      ></RenameModal>
      <FileUploadModal
        visible={documentUploadVisible}
        hideModal={hideDocumentUploadModal}
        loading={documentUploadLoading}
        onOk={onDocumentUploadOk}
        uploadFileList={uploadFileList}
        setUploadFileList={setUploadFileList}
        uploadProgress={uploadProgress}
        setUploadProgress={setUploadProgress}
      ></FileUploadModal>
      <WebCrawlModal
        visible={webCrawlUploadVisible}
        hideModal={hideWebCrawlUploadModal}
        loading={webCrawlUploadLoading}
        onOk={onWebCrawlUploadOk}
      ></WebCrawlModal>
      {setMetaVisible && (
        <SetMetaModal
          visible={setMetaVisible}
          hideModal={hideSetMetaModal}
          onOk={onSetMetaModalOk}
          loading={setMetaLoading}
          initialMetaData={currentRecord.meta_fields}
        ></SetMetaModal>
      )}
    </div>
  );
};

export default KnowledgeFile;
