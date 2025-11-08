import React from 'react';
import {
  Badge,
  Box,
  Button,
  Divider,
  HStack,
  IconButton,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useBreakpointValue,
  useDisclosure,
  useToast,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';  
import { FiTrash, FiInfo, FiBookOpen } from 'react-icons/fi';  
import axios from 'axios';  
import { formatDistance } from 'date-fns';  
import ProgressBar from './ProgressBar';  
import { fetchDocumentMarkdown } from '../api/documents';
import ReactMarkdown from 'react-markdown';


const FileListComponent = ({ documents, onDeleteDocument, showProgress }) => {  
  const toast = useToast();  
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [markdownContent, setMarkdownContent] = React.useState(null);
  const [selectedDocument, setSelectedDocument] = React.useState(null);
  const [loadingMarkdown, setLoadingMarkdown] = React.useState(false);
  const isMobileLayout = useBreakpointValue({ base: true, md: false });

  const handleDelete = async (id, filename) => {  
    try {  
      await axios.delete(`/api/documents/${id}`);  
      toast({  
        title: "Document deleted",  
        description: `${filename} has been deleted successfully`,  
        status: "success",  
        duration: 3000,  
        isClosable: true,  
      });  
      if (onDeleteDocument) onDeleteDocument();  
    } catch (error) {  
      console.error("Delete error:", error);  
      toast({  
        title: "Delete failed",  
        description: error.response?.data?.detail || "Failed to delete document",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    }  
  };  

  const formatFileSize = (bytes) => {  
    if (bytes < 1024) return bytes + ' B';  
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';  
    else return (bytes / 1048576).toFixed(1) + ' MB';  
  };  

  const getStatusBadge = (doc) => {  
    if (doc.error) {  
      return <Badge colorScheme="red">Error</Badge>;  
    }  
    
    if (doc.processed) {  
      return <Badge colorScheme="green">Completed</Badge>;  
    }  
    
    if (doc.processing) {  
      return <Badge colorScheme="blue">Processing</Badge>;  
    }  
    
    return <Badge colorScheme="yellow">Queued</Badge>;  
  };  

  const handleViewMarkdown = async (doc) => {
    setSelectedDocument(doc);
    setLoadingMarkdown(true);
    setMarkdownContent(null);
    onOpen();

    try {
      const data = await fetchDocumentMarkdown({ id: doc.id });
      setMarkdownContent(data.markdown);
    } catch (error) {
      console.error('Failed to fetch markdown:', error);
      setMarkdownContent(null);
      toast({
        title: 'Unable to render markdown',
        description: error.response?.data?.detail || 'Markdown rendering failed',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onClose();
    } finally {
      setLoadingMarkdown(false);
    }
  };

  const renderDesktopTable = () => (
    <Box overflowX="auto">
      <Table variant="simple" size="sm">
        <Thead>  
          <Tr>  
            <Th>Filename</Th>  
            <Th>Uploaded</Th>  
            <Th>Size</Th>  
            <Th>Status</Th>  
            {showProgress && (<Th>Progress</Th>)}  
            <Th>Actions</Th>  
          </Tr>  
        </Thead>  
        <Tbody>  
          {documents.map((doc) => (  
            <Tr key={doc.id}>  
              <Td fontWeight="medium">{doc.filename}</Td>  
              <Td>  
                {formatDistance(new Date(doc.uploaded_at), new Date(), { addSuffix: true })}  
              </Td>  
              <Td>{formatFileSize(doc.file_size)}</Td>  
              <Td>  
                <HStack spacing={2}>  
                  {getStatusBadge(doc)}  
                  {doc.error && (  
                    <Tooltip label={doc.error}>  
                      <IconButton  
                        icon={<FiInfo />}  
                        aria-label="Error details"  
                        size="xs"  
                        colorScheme="red"  
                        variant="ghost"  
                      />  
                    </Tooltip>  
                  )}  
                </HStack>  
              </Td>  
              {showProgress && (  
                <Td>  
                  <Box>  
                    <ProgressBar  
                      progress={doc.progress}  
                      status={doc.statusText}  
                      colorScheme={doc.error ? "red" : "blue"}  
                      pageCurrent={doc.pageCurrent}  
                      pageTotal={doc.pageTotal}  
                    />  
                  </Box>  
                </Td>  
              )}  
              <Td>
                <HStack spacing={2} justify="flex-end">
                  <Button
                    size="sm"
                    leftIcon={<FiBookOpen />}
                    variant="ghost"
                    colorScheme="purple"
                    isDisabled={!doc.processed || !!doc.error || doc.blacklisted}
                    onClick={() => handleViewMarkdown(doc)}
                  >
                    View Markdown
                  </Button>
                  <IconButton  
                    icon={<FiTrash />}  
                    aria-label="Delete document"  
                    size="sm"  
                    colorScheme="red"  
                    variant="ghost"  
                    isDisabled={doc.processing}  
                    onClick={() => handleDelete(doc.id, doc.filename)}  
                  />
                </HStack>
              </Td>
            </Tr>  
          ))}  
        </Tbody>  
      </Table>  
    </Box>
  );

  const renderMobileCards = () => (
    <Stack spacing={4}>
      {documents.map((doc) => (
        <Box
          key={doc.id}
          borderWidth="1px"
          borderRadius="lg"
          p={4}
          bg="white"
          shadow="sm"
        >
          <Stack spacing={3}>
            <Box>
              <Text fontWeight="semibold" noOfLines={2}>{doc.filename}</Text>
              <Wrap spacing={2} mt={1} shouldWrapChildren>
                <WrapItem>{getStatusBadge(doc)}</WrapItem>
                <WrapItem>
                  <Text fontSize="xs" color="gray.500">
                    {formatDistance(new Date(doc.uploaded_at), new Date(), { addSuffix: true })}
                  </Text>
                </WrapItem>
              </Wrap>
              <Text fontSize="sm" color="gray.600" mt={1}>
                {formatFileSize(doc.file_size)}
              </Text>
            </Box>

            {showProgress && (
              <ProgressBar
                progress={doc.progress}
                status={doc.statusText}
                colorScheme={doc.error ? 'red' : 'blue'}
                pageCurrent={doc.pageCurrent}
                pageTotal={doc.pageTotal}
              />
            )}

            {doc.error && (
              <Text fontSize="sm" color="red.500">{doc.error}</Text>
            )}

            <Divider />

            <Stack direction={{ base: 'column', sm: 'row' }} spacing={2} justify="space-between">
              <Button
                leftIcon={<FiBookOpen />}
                variant="solid"
                colorScheme="purple"
                isDisabled={!doc.processed || !!doc.error || doc.blacklisted}
                onClick={() => handleViewMarkdown(doc)}
              >
                View Markdown
              </Button>
              <Button
                leftIcon={<FiTrash />}
                variant="outline"
                colorScheme="red"
                isDisabled={doc.processing}
                onClick={() => handleDelete(doc.id, doc.filename)}
              >
                Delete
              </Button>
            </Stack>
          </Stack>
        </Box>
      ))}
    </Stack>
  );

  return (
    <Box>
      {isMobileLayout ? renderMobileCards() : renderDesktopTable()}
      <Modal isOpen={isOpen} onClose={onClose} size="5xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedDocument ? `Markdown view: ${selectedDocument.filename}` : 'Markdown view'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {loadingMarkdown ? (
              <Box textAlign="center" py={8}>
                <Spinner size="xl" />
                <Text mt={4}>Generating markdown...</Text>
              </Box>
            ) : markdownContent ? (
              <Box
                maxHeight="60vh"
                overflowY="auto"
                borderWidth="1px"
                borderRadius="md"
                p={4}
                bg="gray.50"
              >
                <ReactMarkdown>{markdownContent}</ReactMarkdown>
              </Box>
            ) : (
              <Text color="red.500">No markdown content available.</Text>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={onClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );  
};  

FileListComponent.displayName = 'FileList';

export default React.memo(FileListComponent);