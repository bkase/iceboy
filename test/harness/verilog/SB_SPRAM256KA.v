`ifdef __ICARUS__
module SB_SPRAM256KA(
    input  wire [13:0] ADDRESS,
    input  wire [15:0] DATAIN,
    input  wire [3:0]  MASKWREN,
    input  wire        WREN,
    input  wire        CHIPSELECT,
    input  wire        CLOCK,
    input  wire        STANDBY,
    input  wire        SLEEP,
    input  wire        POWEROFF,
    output reg  [15:0] DATAOUT
);
    reg [15:0] mem [0:16383];
    integer i;
    initial begin
        for (i = 0; i < 16384; i = i + 1) begin
            mem[i] = 16'h0000;
        end
        DATAOUT = 16'h0000;
    end

    always @(posedge CLOCK) begin
        if (!POWEROFF || STANDBY || SLEEP) begin
            DATAOUT <= 16'h0000;
        end else if (CHIPSELECT) begin
            DATAOUT <= mem[ADDRESS];
            if (WREN) begin
                if (MASKWREN[0]) mem[ADDRESS][3:0] <= DATAIN[3:0];
                if (MASKWREN[1]) mem[ADDRESS][7:4] <= DATAIN[7:4];
                if (MASKWREN[2]) mem[ADDRESS][11:8] <= DATAIN[11:8];
                if (MASKWREN[3]) mem[ADDRESS][15:12] <= DATAIN[15:12];
            end
        end
    end
endmodule
`elsif VERILATOR
module SB_SPRAM256KA(
    input  wire [13:0] ADDRESS,
    input  wire [15:0] DATAIN,
    input  wire [3:0]  MASKWREN,
    input  wire        WREN,
    input  wire        CHIPSELECT,
    input  wire        CLOCK,
    input  wire        STANDBY,
    input  wire        SLEEP,
    input  wire        POWEROFF,
    output reg  [15:0] DATAOUT
);
    reg [15:0] mem [0:16383];
    integer i;
    initial begin
        for (i = 0; i < 16384; i = i + 1) begin
            mem[i] = 16'h0000;
        end
        DATAOUT = 16'h0000;
    end

    always @(posedge CLOCK) begin
        if (!POWEROFF || STANDBY || SLEEP) begin
            DATAOUT <= 16'h0000;
        end else if (CHIPSELECT) begin
            DATAOUT <= mem[ADDRESS];
            if (WREN) begin
                if (MASKWREN[0]) mem[ADDRESS][3:0] <= DATAIN[3:0];
                if (MASKWREN[1]) mem[ADDRESS][7:4] <= DATAIN[7:4];
                if (MASKWREN[2]) mem[ADDRESS][11:8] <= DATAIN[11:8];
                if (MASKWREN[3]) mem[ADDRESS][15:12] <= DATAIN[15:12];
            end
        end
    end
endmodule
`endif
