import { MessageType } from '@/constants/chat';
import { useFetchFlow } from '@/hooks/flow-hooks';
import {
  useHandleMessageInputChange,
  useSelectDerivedMessages,
  useSendMessageWithSse,
} from '@/hooks/logic-hooks';
import { Message } from '@/interfaces/database/chat';
import api from '@/utils/api';
import { message } from 'antd';
import trim from 'lodash/trim';
import { useCallback, useEffect } from 'react';
import { useParams } from 'umi';
import { v4 as uuid } from 'uuid';
import { receiveMessageError } from '../utils';

const antMessage = message;

export const useSelectNextMessages = () => {
  const { data: flowDetail, loading } = useFetchFlow();
  const reference = flowDetail.dsl.reference;
  const {
    derivedMessages,
    ref,
    addNewestQuestion,
    addNewestAnswer,
    removeLatestMessage,
    removeMessageById,
    removeMessagesAfterCurrentMessage,
  } = useSelectDerivedMessages();

  return {
    reference,
    loading,
    derivedMessages,
    ref,
    addNewestQuestion,
    addNewestAnswer,
    removeLatestMessage,
    removeMessageById,
    removeMessagesAfterCurrentMessage,
  };
};

export const useSendNextMessage = () => {
  const {
    reference,
    loading,
    derivedMessages,
    ref,
    addNewestQuestion,
    addNewestAnswer,
    removeLatestMessage,
    removeMessageById,
  } = useSelectNextMessages();
  const { id: flowId } = useParams();
  const { handleInputChange, value, setValue } = useHandleMessageInputChange();
  const { refetch } = useFetchFlow();

  const { send, answer, done } = useSendMessageWithSse(api.runCanvas);

  const sendMessage = useCallback(
    async ({
      message,
      images,
    }: {
      message: Message;
      messages?: Message[];
      images?: any[];
    }) => {
      const params: Record<string, unknown> = {
        id: flowId,
      };
      if (message.content) {
        params.message = message.content;
        params.message_id = message.id;
      }

      // 添加图片数据
      if (images && images.length > 0) {
        params.images = images;
      }

      const res = await send(params);

      if (receiveMessageError(res)) {
        antMessage.error(res?.data?.message);

        // cancel loading
        setValue(message.content);
        removeLatestMessage();
      } else {
        refetch(); // pull the message list after sending the message successfully
      }
    },
    [flowId, send, setValue, removeLatestMessage, refetch],
  );

  const handleSendMessage = useCallback(
    async (message: Message, images?: any[]) => {
      sendMessage({ message, images });
    },
    [sendMessage],
  );

  useEffect(() => {
    if (answer.answer) {
      addNewestAnswer(answer);
    }
  }, [answer, addNewestAnswer]);

  const handlePressEnter = useCallback(
    (documentIds: string[] = [], images?: any[]) => {
      if (trim(value) === '' && (!images || images.length === 0)) return;
      const id = uuid();
      if (done) {
        setValue('');
        handleSendMessage(
          { id, content: value.trim(), role: MessageType.User },
          images,
        );
      }
      addNewestQuestion({
        content: value,
        id,
        role: MessageType.User,
        // 将图片信息添加到消息中，以便前端显示
        images: images?.map((img) => ({
          name: img.name,
          url: img.data,
        })),
      });
    },
    [addNewestQuestion, handleSendMessage, done, setValue, value],
  );

  const fetchPrologue = useCallback(async () => {
    // fetch prologue
    const sendRet = await send({ id: flowId });
    if (receiveMessageError(sendRet)) {
      message.error(sendRet?.data?.message);
    } else {
      refetch();
    }
  }, [flowId, refetch, send]);

  useEffect(() => {
    fetchPrologue();
  }, [fetchPrologue]);

  return {
    handlePressEnter,
    handleInputChange,
    value,
    sendLoading: !done,
    reference,
    loading,
    derivedMessages,
    ref,
    removeMessageById,
  };
};
