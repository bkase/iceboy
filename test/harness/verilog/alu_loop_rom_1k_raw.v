module alu_loop_rom_raw_1k(
    input wire CLK,
    input wire [9:0] CPU_ADDR,
    output reg [7:0] CPU_DATA
);
    (* ram_style = "block" *) reg [7:0] rom [0:1023];
    initial begin
`ifdef SYNTHESIS
        $readmemh("test/harness/verilog/alu_loop_rom_1k.mem", rom);
`else
        integer mem_fd;
        mem_fd = $fopen("test/harness/verilog/alu_loop_rom_1k.mem", "r");
        if (mem_fd != 0) begin
            $fclose(mem_fd);
            $readmemh("test/harness/verilog/alu_loop_rom_1k.mem", rom);
        end else begin
            mem_fd = $fopen("../../../test/harness/verilog/alu_loop_rom_1k.mem", "r");
            if (mem_fd != 0) begin
                $fclose(mem_fd);
                $readmemh("../../../test/harness/verilog/alu_loop_rom_1k.mem", rom);
            end else begin
                mem_fd = $fopen("../../../../test/harness/verilog/alu_loop_rom_1k.mem", "r");
                if (mem_fd != 0) begin
                    $fclose(mem_fd);
                    $readmemh("../../../../test/harness/verilog/alu_loop_rom_1k.mem", rom);
                end else begin
                    $error("alu_loop_rom_1k.mem not found");
                end
            end
        end
`endif
    end

    always @(posedge CLK) begin
        CPU_DATA <= rom[CPU_ADDR];
    end
endmodule
