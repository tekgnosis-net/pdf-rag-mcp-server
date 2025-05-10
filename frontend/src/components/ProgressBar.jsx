import React, { useMemo } from 'react';  
import {  
  Box,  
  Progress,  
  Text,  
  HStack,  
  Tooltip,  
  Badge  
} from '@chakra-ui/react';  

const ProgressBar = ({ progress = 0, status = "Processing..." }) => {  
  const value = Math.max(0, Math.min(100, progress));  
  
  // Set progress bar color  
  const colorScheme = useMemo(() => {  
    if (status.toLowerCase().includes('error')) return 'red';  
    if (value === 100) return 'green';  
    return 'blue';  
  }, [value, status]);  
  
  // Format status text  
  const statusText = useMemo(() => {  
    if (status.toLowerCase().includes('error')) {  
      return status.replace('Error:', 'Error:');  
    }  
    return status;  
  }, [status]);  

  return (  
    <Box width="100%">  
      <HStack mb={1} justify="space-between">  
        {status && (  
          <Tooltip label={statusText}>  
            <Badge colorScheme={colorScheme} fontSize="xs">  
              {statusText.length > 20 ? `${statusText.substring(0, 20)}...` : statusText}  
            </Badge>  
          </Tooltip>  
        )}  
        
        <Text fontSize="xs" fontWeight="medium" ml="auto">  
          {Math.round(value)}%  
        </Text>  
      </HStack>  
      
      <Progress   
        value={value}   
        size="md"   
        colorScheme={colorScheme}  
        borderRadius="full"  
        hasStripe={value < 100 && value > 0}  
        isAnimated={value < 100 && value > 0}  
      />  
    </Box>  
  );  
};  

export default ProgressBar;