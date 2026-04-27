# based on Piko stats Home https://sourceforge.net/projects/piko/

import socket
import logging

def CalcChkSum(Packet):
    Chk = 0
    if len(Packet) == 0: return 0
    for i in range(len(Packet)):
        Chk -= Packet[i]
        Chk %= 256
    return Chk

def ChkSum(Packet):
    Chk = 0
    if len(Packet) == 0: return 0
    for i in range(len(Packet)):
        Chk += Packet[i]
        Chk %= 256
    if Chk == 0:
        return 1
    else:
        return 0

def GetWord(Packet, Idx):
    Val = 0
    Val = Packet[Idx] + 256 * Packet[Idx+1]
    return Val

def GetDWord(Packet, Idx):
    Val = 0
    Val = Packet[Idx] + 256 * Packet[Idx+1] + 65536 * Packet[Idx+2] + 256 * 65536 * Packet[Idx+3]
    return Val

def CnvStatusTxt(Val):
    Txt = "Communication error"
    if Val == 0: Txt = "Off"
    if Val == 1: Txt = "Idle"
    if Val == 2: Txt = "Starting"
    if Val == 3: Txt = "Running-MPP"
    if Val == 4: Txt = "Running-Regulated"
    if Val == 5: Txt = "Running"
    return Txt

class DevState:
    WaitForDevice = 0
    disconnected = 1
    Connected = 2



class DevStatistics:
    connection_errors = 0
    last_connection_errors = 0  # reset every ok read
    last_time = 0
    reconnect = 0
    
    
class KostalSocket:
    host = ''
    port = 81
    busAddr = 255
    stats = DevStatistics
    interval = 10
    intervall_active = 10
    version = 1
    instance = 50
    max_retries = 10
    inverter_name = 'NO_NAME_PROVIDED'
    model = ''
    sw_version = ''
    position = 0
    dev_state = DevState.WaitForDevice
    
    s= None
    
    def __init__(self, host, port, addr, instance, interval, position):
        self.host = host
        self.port = int(port)
        self.busAddr = int(addr)
        self.instance = instance
        self.interval = self.intervall_active = interval
        self.position = position
    
    def __del__(self):
        self.disconnect()
   
    def disconnect(self):
        if self.s is not None:
            self.s.close()
            self.s = None
        self.dev_state = DevState.disconnected
        self.stats.last_connection_errors = 0
            
    def connect(self):
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.settimeout(5)
            self.s.connect((self.host, self.port))
            self.s.settimeout(1)
            self.dev_state = DevState.Connected          
            
        except socket.error as msg:
            logging.error("Socket connect error: {}".format(msg))
            self.dev_state = DevState.WaitForDevice
            return False
        return True
        
    def SndRecv(self, Snd) :
        Snd=b'\x62'+bytes([self.busAddr])+b'\x03'+bytes([self.busAddr])+Snd
        Snd+=bytes([CalcChkSum(Snd)])+b"\x00"
        
        i = 0
        Recv = b''
        data = b''
        try :
            self.s.send(Snd)
            Recv = self.s.recv(4096)
        except :
            return ""     
        # while (1):
        #     try :
        #         data = self.s.recv(4096)
        #     except :
        #         Recv += data
        #         break
        #     if (i < 5):
        #         Recv += data
        #         data = b''
        #     if not data:
        #         break
        if (len(Recv)>0) and (Recv[0]==255):
            Recv=""
        return Recv
        
        
    def initCommonData(self):
        InvName = ""
        if self.dev_state == DevState.Connected:
            Recv=self.SndRecv(b"\x00\x44")
            if ChkSum(Recv) != 0 and len(Recv)>=20:
                for i in range(15):
                    if 0x20 <= Recv[5+i] <= 0x7f: InvName+=chr(Recv[5+i])
                self.inverter_name= InvName
                    
            # Get Inverter Model
            InvModel = ""
            InvString = 1
            InvPhase = 1
            Recv=self.SndRecv(b"\x00\x90")
            if ChkSum(Recv) != 0 and len(Recv)>=21:
                for i in range(16):
                    if 0x20 <= Recv[5+i] <= 0x7f: InvModel+=chr(Recv[5+i])
                self.model= InvModel
                InvString = Recv[5+16]
                InvPhase = Recv[5+23]                    
                    
            # Get Inverter SN
            InvSN = ""; InvRef = ""
            Recv=self.SndRecv(b"\x00\x50")
            if ChkSum(Recv) != 0:
                if len(Recv) == 20:
                    for i in range(13):
                        if 0x20 <= Recv[5+i] <= 0x7f: InvSN+=chr(Recv[5+i])
                if len(Recv) == 12:
                    SN1=Recv[5]; SN2=Recv[6]; SN3=Recv[7]; SN4=Recv[8]; SN5=Recv[9]
                    InvSN+="%1x%1x%1x%1x%1x%1x%1x%1x%1x" % (SN1//16, SN1%16, SN3%16, SN2//16, SN2%16, SN5//16, SN5%16, SN4//16, SN4%16)
                self.sw_version = InvSN
        return InvName != ""
               
    def getData(self):        
        data = {"status":10, "Error":""}

        try:
            if self.dev_state != DevState.Connected:
                self.stats.reconnect += 1
                if not self.connect():
                    return data

            Recv=self.SndRecv(b'\x00\x57')
            if Recv == "":  # connection error
                self.stats.connection_errors += 1
                self.stats.last_connection_errors += 1
                self.dev_state = DevState.WaitForDevice
                return data   
            
            Status = -1; 
            ErrorCode= -1;
            Error = "";
            if ChkSum(Recv) != 0:                    
                Status = Recv[5]
                Error = Recv[6]
                ErrorCode = GetWord(Recv, 7)
                
            if Status == 3:
                data['status'] = 11 #Running-MPP, 
                self.interval = self.intervall_active # reset interval to active
            elif Status >3 and Status <= 5: 
                data['status'] = 7 # Running-Regulated, Running 
                self.interval = self.intervall_active # reset interval to active
            elif Status <= 1: 
                data['status'] = 8 # Idle -> Standby
                self.interval = 5 * 60 # increase interval to 5 minutes
            elif Status == 2 : 
                data['status'] = 1 # Starting
            else:
                data['status'] = 10 # Error
                data['Error'] = "Status: " + CnvStatusTxt(Status) + ", Error: " +  Error + ", code: " + ErrorCode
            if (Status > 5): 
                return data
            #StatusTxt = CnvStatusTxt(Status)

            Recv=self.SndRecv(b"\x00\x43")
            if ChkSum(Recv) != 0 and (len(Recv)>65):
                data['VA'] = GetWord(Recv, 35)*1.0/10 # round(getProcessDataValue('L1_U'), 1)
                data['PA'] = GetWord(Recv, 39) # round(getProcessDataValue('L1_P'), 1)
                data['IA'] = GetWord(Recv, 37)*1.0/100 # round(getProcessDataValue('L1_I'), 1)
                data['VB'] = GetWord(Recv, 43)*1.0/10 # round(getProcessDataValue('L2_U'), 1)
                data['PB'] = GetWord(Recv, 47) # round(getProcessDataValue('L2_P'), 1)
                data['IB'] = GetWord(Recv, 45)*1.0/100 # round(getProcessDataValue('L2_I'), 1)
                data['VC'] = GetWord(Recv, 51)*1.0/10 # round(getProcessDataValue('L3_U'), 1)
                data['PC'] = GetWord(Recv, 55) #round(getProcessDataValue('L3_P'), 1)
                data['IC'] = GetWord(Recv, 53)*1.0/100 # round(getProcessDataValue('L3_I'), 1)
                
                data['PT'] = data['PA'] + data['PB'] + data['PC']
                #data['IN0'] = round(data['IA'] + data['IB'] + data['IC'], 1)
                
                Recv=self.SndRecv(b"\x00\x45")
                if ChkSum(Recv) != 0:
                    data['EFAT'] =round(GetDWord(Recv, 5)/1000,3)
        except Exception as msg:
            logging.error("could not read data: {}".format(msg))

        return data
