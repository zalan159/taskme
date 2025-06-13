import { useTranslate } from '@/hooks/common-hooks';
import {
  useDeleteDocument,
  useFetchDocumentInfosByIds,
  useRemoveNextDocument,
  useUploadAndParseDocument,
} from '@/hooks/document-hooks';
import { getExtension } from '@/utils/document-util';
import { formatBytes } from '@/utils/file-util';
import {
  CloseCircleOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  PictureOutlined,
  SendOutlined,
} from '@ant-design/icons';
import type { RcFile, UploadFile, UploadProps } from 'antd';
import {
  Button,
  Card,
  Divider,
  Flex,
  Input,
  List,
  Space,
  Spin,
  Typography,
  Upload,
} from 'antd';
import get from 'lodash/get';
import {
  ChangeEventHandler,
  memo,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import FileIcon from '../file-icon';
import styles from './index.less';

type FileType = RcFile;
const { Text } = Typography;

const { TextArea } = Input;

const getFileId = (file: UploadFile) => get(file, 'response.data.0');

const getFileIds = (fileList: UploadFile[]) => {
  const ids = fileList.reduce((pre, cur) => {
    return pre.concat(get(cur, 'response.data', []));
  }, []);

  return ids;
};

const isUploadSuccess = (file: UploadFile) => {
  const code = get(file, 'response.code');
  return typeof code === 'number' && code === 0;
};

interface IProps {
  disabled: boolean;
  value: string;
  sendDisabled: boolean;
  sendLoading: boolean;
  onPressEnter(documentIds: string[], images?: any[]): void;
  onInputChange: ChangeEventHandler<HTMLTextAreaElement>;
  conversationId: string;
  uploadMethod?: string;
  isShared?: boolean;
  showUploadIcon?: boolean;
  showImageUploadIcon?: boolean;
  createConversationBeforeUploadDocument?(message: string): Promise<any>;
}

const getBase64 = (file: FileType): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file as any);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(error);
  });

const MessageInput = ({
  isShared = false,
  disabled,
  value,
  onPressEnter,
  sendDisabled,
  sendLoading,
  onInputChange,
  conversationId,
  showUploadIcon = true,
  showImageUploadIcon = true,
  createConversationBeforeUploadDocument,
  uploadMethod = 'upload_and_parse',
}: IProps) => {
  const { t } = useTranslate('chat');
  const { removeDocument } = useRemoveNextDocument();
  const { deleteDocument } = useDeleteDocument();
  const { data: documentInfos, setDocumentIds } = useFetchDocumentInfosByIds();
  const { uploadAndParseDocument } = useUploadAndParseDocument(uploadMethod);
  const conversationIdRef = useRef(conversationId);

  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [imageList, setImageList] = useState<any[]>([]);

  const handlePreview = async (file: UploadFile) => {
    if (!file.url && !file.preview) {
      file.preview = await getBase64(file.originFileObj as FileType);
    }
  };

  const handleChange: UploadProps['onChange'] = async ({ file }) => {
    let nextConversationId: string = conversationId;
    if (createConversationBeforeUploadDocument) {
      const creatingRet = await createConversationBeforeUploadDocument(
        file.name,
      );
      if (creatingRet?.code === 0) {
        nextConversationId = creatingRet.data.id;
      }
    }
    setFileList((list) => {
      list.push({
        ...file,
        status: 'uploading',
        originFileObj: file as any,
      });
      return [...list];
    });
    const ret = await uploadAndParseDocument({
      conversationId: nextConversationId,
      fileList: [file],
    });
    setFileList((list) => {
      const nextList = list.filter((x) => x.uid !== file.uid);
      nextList.push({
        ...file,
        originFileObj: file as any,
        response: ret,
        percent: 100,
        status: ret?.code === 0 ? 'done' : 'error',
      });
      return nextList;
    });
  };

  // 处理图片上传
  const handleImageUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    try {
      // 使用FileReader读取文件内容为base64
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const base64Data = reader.result as string;
        // 添加到图片列表
        setImageList((prevList) => [
          ...prevList,
          {
            uid: file.uid,
            name: file.name,
            data: base64Data,
            status: 'done',
            url: base64Data,
          },
        ]);
        onSuccess({ code: 0, data: base64Data });
      };
      reader.onerror = (error) => {
        onError(error);
      };
    } catch (error) {
      onError(error);
    }
  };

  const handleImageRemove = (file: any) => {
    setImageList((prevList) =>
      prevList.filter((item) => item.uid !== file.uid),
    );
    return true;
  };

  const isUploadingFile = fileList.some((x) => x.status === 'uploading');

  const handleKeyDown = useCallback(
    async (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // check if it was shift + enter
      if (event.key === 'Enter' && event.shiftKey) return;
      if (event.key !== 'Enter') return;
      if (sendDisabled || isUploadingFile || sendLoading) return;

      event.preventDefault();
      handlePressEnter();
    },
    [fileList, onPressEnter, isUploadingFile],
  );

  const handlePressEnter = useCallback(async () => {
    if (isUploadingFile) return;
    const ids = getFileIds(fileList.filter((x) => isUploadSuccess(x)));

    // 准备图片数据
    const images = imageList.map((img) => ({
      name: img.name,
      data: img.data,
    }));

    onPressEnter(ids, images);
    setFileList([]);
    setImageList([]);
  }, [fileList, imageList, onPressEnter, isUploadingFile]);

  const [isComposing, setIsComposing] = useState(false);

  const handleCompositionStart = () => setIsComposing(true);
  const handleCompositionEnd = () => setIsComposing(false);

  const handleRemove = useCallback(
    async (file: UploadFile) => {
      const ids = get(file, 'response.data', []);
      // Upload Successfully
      if (Array.isArray(ids) && ids.length) {
        if (isShared) {
          await deleteDocument(ids);
        } else {
          await removeDocument(ids[0]);
        }
        setFileList((preList) => {
          return preList.filter((x) => getFileId(x) !== ids[0]);
        });
      } else {
        // Upload failed
        setFileList((preList) => {
          return preList.filter((x) => x.uid !== file.uid);
        });
      }
    },
    [removeDocument, deleteDocument, isShared],
  );

  const getDocumentInfoById = useCallback(
    (id: string) => {
      return documentInfos.find((x) => x.id === id);
    },
    [documentInfos],
  );

  useEffect(() => {
    const ids = getFileIds(fileList);
    setDocumentIds(ids);
  }, [fileList, setDocumentIds]);

  useEffect(() => {
    if (
      conversationIdRef.current &&
      conversationId !== conversationIdRef.current
    ) {
      setFileList([]);
    }
    conversationIdRef.current = conversationId;
  }, [conversationId, setFileList]);

  return (
    <Flex gap={1} vertical className={styles.messageInputWrapper}>
      <TextArea
        size="large"
        placeholder={t('sendPlaceholder')}
        value={value}
        allowClear
        disabled={disabled}
        style={{
          border: 'none',
          boxShadow: 'none',
          padding: '0px 10px',
          marginTop: 10,
        }}
        autoSize={{ minRows: 2, maxRows: 10 }}
        onKeyDown={handleKeyDown}
        onChange={onInputChange}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
      />
      <Divider style={{ margin: '5px 30px 10px 0px' }} />
      <Flex justify="space-between" align="center">
        {(fileList.length > 0 || imageList.length > 0) && (
          <List
            grid={{
              gutter: 16,
              xs: 1,
              sm: 1,
              md: 1,
              lg: 1,
              xl: 2,
              xxl: 4,
            }}
            dataSource={[...fileList, ...imageList]}
            className={styles.listWrapper}
            renderItem={(item) => {
              // 处理图片预览
              if (item.url) {
                return (
                  <List.Item>
                    <Card className={styles.documentCard}>
                      <Flex gap={10} align="center">
                        <img
                          src={item.url}
                          alt={item.name}
                          style={{ width: 40, height: 40, objectFit: 'cover' }}
                        />
                        <Flex vertical style={{ width: '90%' }}>
                          <Text
                            ellipsis={{ tooltip: item.name }}
                            className={styles.nameText}
                          >
                            <b>{item.name}</b>
                          </Text>
                          <span>图片</span>
                        </Flex>
                      </Flex>

                      <span className={styles.deleteIcon}>
                        <CloseCircleOutlined
                          onClick={() => handleImageRemove(item)}
                        />
                      </span>
                    </Card>
                  </List.Item>
                );
              }

              // 处理文件预览
              const id = getFileId(item);
              const documentInfo = getDocumentInfoById(id);
              const fileExtension = getExtension(documentInfo?.name ?? '');
              const fileName = item.originFileObj?.name ?? '';

              return (
                <List.Item>
                  <Card className={styles.documentCard}>
                    <Flex gap={10} align="center">
                      {item.status === 'uploading' ? (
                        <Spin
                          indicator={
                            <LoadingOutlined style={{ fontSize: 24 }} spin />
                          }
                        />
                      ) : item.status === 'error' ? (
                        <InfoCircleOutlined size={30}></InfoCircleOutlined>
                      ) : (
                        <FileIcon id={id} name={fileName}></FileIcon>
                      )}
                      <Flex vertical style={{ width: '90%' }}>
                        <Text
                          ellipsis={{ tooltip: fileName }}
                          className={styles.nameText}
                        >
                          <b> {fileName}</b>
                        </Text>
                        {item.status === 'error' ? (
                          t('uploadFailed')
                        ) : (
                          <>
                            {item.percent !== 100 ? (
                              t('uploading')
                            ) : !item.response ? (
                              t('parsing')
                            ) : (
                              <Space>
                                <span>{fileExtension?.toUpperCase()},</span>
                                <span>
                                  {formatBytes(
                                    getDocumentInfoById(id)?.size ?? 0,
                                  )}
                                </span>
                              </Space>
                            )}
                          </>
                        )}
                      </Flex>
                    </Flex>

                    {item.status !== 'uploading' && (
                      <span className={styles.deleteIcon}>
                        <CloseCircleOutlined
                          onClick={() => handleRemove(item)}
                        />
                      </span>
                    )}
                  </Card>
                </List.Item>
              );
            }}
          />
        )}
        <Flex
          gap={5}
          align="center"
          justify="flex-end"
          style={{
            paddingRight: 10,
            paddingBottom: 10,
            width: fileList.length > 0 || imageList.length > 0 ? '50%' : '100%',
          }}
        >
          {showImageUploadIcon && (
            <Upload
              customRequest={handleImageUpload}
              showUploadList={false}
              accept="image/*"
              onRemove={handleImageRemove}
              disabled={disabled}
            >
              <Button type={'primary'} disabled={disabled}>
                <PictureOutlined />
              </Button>
            </Upload>
          )}
          {showUploadIcon && (
            <Upload
              onPreview={handlePreview}
              onChange={handleChange}
              multiple={false}
              onRemove={handleRemove}
              showUploadList={false}
              beforeUpload={() => {
                return false;
              }}
            >
              <Button type={'primary'} disabled={disabled}>
                <PaperClipOutlined />
              </Button>
            </Upload>
          )}
          <Button
            type="primary"
            onClick={handlePressEnter}
            loading={sendLoading}
            disabled={sendDisabled || isUploadingFile || sendLoading}
          >
            <SendOutlined />
          </Button>
        </Flex>
      </Flex>
    </Flex>
  );
};

export default memo(MessageInput);
