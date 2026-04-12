module rom_baked_ebr_sync_file #(
    parameter integer ADDR_BITS = 10,
    parameter integer DEPTH = 1024,
    parameter INIT_FILE = ""
) (
    input wire CLK,
    input wire [ADDR_BITS-1:0] CPU_ADDR,
    output reg [7:0] CPU_DATA
);
    (* ram_style = "block" *) reg [7:0] rom [0:DEPTH-1];
    integer i;

    function [7:0] baked_pattern;
        input integer index;
        begin
            baked_pattern = ((index * 37) + 8'h11) & 8'hff;
        end
    endfunction

    initial begin
        for (i = 0; i < DEPTH; i = i + 1) begin
            rom[i] = baked_pattern(i);
        end
        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, rom);
        end
    end

    always @(posedge CLK) begin
        CPU_DATA <= rom[CPU_ADDR];
    end
endmodule

module rom_baked_ebr_raw_1k(
    input wire CLK,
    input wire [9:0] CPU_ADDR,
    output wire [7:0] CPU_DATA
);
    rom_baked_ebr_sync_file #(
        .ADDR_BITS(10),
        .DEPTH(1024),
        .INIT_FILE("test/harness/verilog/rom_baked_ebr_1k.mem")
    ) impl (
        .CLK(CLK),
        .CPU_ADDR(CPU_ADDR),
        .CPU_DATA(CPU_DATA)
    );
endmodule

module rom_baked_ebr_raw_2k(
    input wire CLK,
    input wire [10:0] CPU_ADDR,
    output wire [7:0] CPU_DATA
);
    rom_baked_ebr_sync_file #(
        .ADDR_BITS(11),
        .DEPTH(2048),
        .INIT_FILE("test/harness/verilog/rom_baked_ebr_2k.mem")
    ) impl (
        .CLK(CLK),
        .CPU_ADDR(CPU_ADDR),
        .CPU_DATA(CPU_DATA)
    );
endmodule

module rom_baked_ebr_raw_4k(
    input wire CLK,
    input wire [11:0] CPU_ADDR,
    output wire [7:0] CPU_DATA
);
    rom_baked_ebr_sync_file #(
        .ADDR_BITS(12),
        .DEPTH(4096),
        .INIT_FILE("test/harness/verilog/rom_baked_ebr_4k.mem")
    ) impl (
        .CLK(CLK),
        .CPU_ADDR(CPU_ADDR),
        .CPU_DATA(CPU_DATA)
    );
endmodule

module rom_baked_ebr_raw_8k(
    input wire CLK,
    input wire [12:0] CPU_ADDR,
    output wire [7:0] CPU_DATA
);
    rom_baked_ebr_sync_file #(
        .ADDR_BITS(13),
        .DEPTH(8192),
        .INIT_FILE("test/harness/verilog/rom_baked_ebr_8k.mem")
    ) impl (
        .CLK(CLK),
        .CPU_ADDR(CPU_ADDR),
        .CPU_DATA(CPU_DATA)
    );
endmodule
