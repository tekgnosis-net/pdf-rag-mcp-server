import React, { useCallback, useState } from 'react';  
import { useDropzone } from 'react-dropzone';  
import {   
  Box,   
  Text,   
  VStack,   
  HStack,   
  Button,   
  useToast,   
  Progress,  
  Icon  
} from '@chakra-ui/react';  
import { FiUpload, FiFile } from 'react-icons/fi';  
import axios from 'axios';  

const FileUpload = ({ onFileUploaded }) => {  
  const [uploading, setUploading] = useState(false);  
  const [uploadProgress, setUploadProgress] = useState(0);  
  const toast = useToast();  

  const onDrop = useCallback(async (acceptedFiles) => {  
    const file = acceptedFiles[0];  
    
    if (!file) return;  
    
    // 检查文件类型  
    if (file.type !== 'application/pdf') {  
      toast({  
        title: "Invalid file type",  
        description: "Only PDF files are accepted",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
      return;  
    }  
    
    setUploading(true);  
    setUploadProgress(0);  
    
    // 创建FormData对象  
    const formData = new FormData();  
    formData.append('file', file);  
    
    try {  
      // 上传文件  
      const response = await axios.post('/api/upload', formData, {  
        headers: {  
          'Content-Type': 'multipart/form-data',  
        },  
        onUploadProgress: (progressEvent) => {  
          const percentCompleted = Math.round(  
            (progressEvent.loaded * 100) / progressEvent.total  
          );  
          setUploadProgress(percentCompleted);  
        },  
      });  
      
      toast({  
        title: "File uploaded",  
        description: response.data.message,  
        status: "success",  
        duration: 5000,  
        isClosable: true,  
      });  
      
      // 通知父组件  
      if (onFileUploaded) {  
        onFileUploaded(response.data);  
      }  
    } catch (error) {  
      console.error("Upload error:", error);  
      toast({  
        title: "Upload failed",  
        description: error.response?.data?.detail || "An error occurred during upload",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    } finally {  
      setUploading(false);  
    }  
  }, [toast, onFileUploaded]);  
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({   
    onDrop,  
    accept: {  
      'application/pdf': ['.pdf'],  
    },  
    multiple: false  
  });  
  
  return (  
    <Box width="100%">  
      <Box  
        {...getRootProps()}  
        p={6}  
        borderWidth={2}  
        borderRadius="md"  
        borderStyle="dashed"  
        borderColor={isDragActive ? "blue.400" : "gray.300"}  
        bg={isDragActive ? "blue.50" : "white"}  
        cursor="pointer"  
        transition="all 0.2s"  
        _hover={{  
          borderColor: "blue.300",  
          bg: "blue.50"  
        }}  
      >  
        <input {...getInputProps()} />  
        <VStack spacing={3}>  
          <Icon as={FiUpload} w={10} h={10} color="gray.400" />  
          <Text textAlign="center" fontWeight="medium">  
            {isDragActive   
              ? "Drop the PDF here..."   
              : "Drag & drop a PDF file here, or click to select"}  
          </Text>  
          <Text fontSize="sm" color="gray.500">  
            Only PDF files are supported  
          </Text>  
        </VStack>  
      </Box>  
      
      {uploading && (  
        <VStack mt={4} spacing={2} align="stretch">  
          <HStack>  
            <Icon as={FiFile} />  
            <Text>Uploading...</Text>  
          </HStack>  
          <Progress value={uploadProgress} size="sm" colorScheme="blue" />  
        </VStack>  
      )}  
    </Box>  
  );  
};  

export default FileUpload;